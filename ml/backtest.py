import pandas as pd
import numpy as np
import json
import os

from feature_engineering import FeatureEngineering
from model_training import HybridPredictionModel
from fetch_historical_data import download_historical_data


# -------------------------------
# Kelly Criterion
# -------------------------------
def kelly_fraction(prob, odds):
    b = odds - 1
    q = 1 - prob

    if b <= 0:
        return 0

    return max(0, (b * prob - q) / b)


# -------------------------------
# Walk-Forward Validation (FIXED)
# -------------------------------
def walk_forward_validation(df, feature_cols):
    print("Starting Walk-Forward Validation...")
    
    split_points = [
        int(len(df)*0.5),
        int(len(df)*0.7),
        int(len(df)*0.85)
    ]
    
    all_probs = []
    all_y_test = []
    all_test_indices = []
    
    for i in range(len(split_points)):
        split = split_points[i]

        # ✅ define proper next split
        if i < len(split_points) - 1:
            next_split = split_points[i + 1]
        else:
            next_split = len(df)

        print(f"Training on first {split} matches...")
        
        train = df.iloc[:split]
        test = df.iloc[split:next_split]   # ✅ FIXED

        if len(test) == 0:
            continue

        X_train = train[feature_cols].values
        y_train = train['target'].values
        
        X_test = test[feature_cols].values
        y_test = test['target'].values
        
        model = HybridPredictionModel()
        model.train(X_train, y_train)
        
        preds = model.predict_proba(X_test)
        
        all_probs.extend(preds)
        all_y_test.extend(y_test)
        all_test_indices.extend(test.index.tolist())
        
        # Save final model
        if i == len(split_points) - 1:
            model.save_model('ensemble_model.pkl')

    return np.array(all_probs), np.array(all_y_test), all_test_indices


# -------------------------------
# Main Backtest Function
# -------------------------------
def run_backtest():
    print("Starting Backtesting Pipeline...")

    # -------------------------------
    # 1. Load Data
    # -------------------------------
    data_path = 'data/historical_matches.csv'

    if not os.path.exists(data_path):
        df = download_historical_data()
    else:
        df = pd.read_csv(data_path)
        df['Date'] = pd.to_datetime(df['Date'])

    if df is None or len(df) == 0:
        print("No data available.")
        return

    # -------------------------------
    # 2. Feature Engineering
    # -------------------------------
    print("Engineering features...")
    fe = FeatureEngineering()
    df_features, feature_cols = fe.create_features(df, is_training=True)

    # -------------------------------
    # 3. Walk-Forward Validation
    # -------------------------------
    probs, y_test, test_indices = walk_forward_validation(df_features, feature_cols)

    # -------------------------------
    # 4. Metrics
    # -------------------------------
    from sklearn.metrics import log_loss, accuracy_score

    preds_class = np.argmax(probs, axis=1)

    # Convert y_test to one-hot
    y_test_dummies = pd.get_dummies(y_test).values

    if y_test_dummies.shape[1] < 3:
        y_full = np.zeros((len(y_test), 3))
        for i, val in enumerate(y_test):
            y_full[i, val] = 1
        y_test_dummies = y_full

    metrics = {
        "log_loss": log_loss(y_test, probs, labels=[0, 1, 2]),
        "brier_score": np.mean(np.sum((probs - y_test_dummies) ** 2, axis=1)),
        "accuracy": accuracy_score(y_test, preds_class)
    }

    # -------------------------------
    # 5. Betting Simulation (FIXED)
    # -------------------------------
    print("Simulating betting strategy...")

    bankroll = 1000.0
    starting_bankroll = bankroll

    bets_placed = 0
    bets_won = 0

    test_df = df_features.loc[test_indices].reset_index(drop=True)

    for i in range(len(test_df)):
        row = test_df.iloc[i]

        if pd.isna(row['B365H']) or pd.isna(row['B365D']) or pd.isna(row['B365A']):
            continue

        # ✅ Correct probability order
        prob_h, prob_d, prob_a = probs[i]

        odds_h = row['B365H']
        odds_d = row['B365D']
        odds_a = row['B365A']

        implied_h = 1 / odds_h
        implied_d = 1 / odds_d
        implied_a = 1 / odds_a

        actual_result = row['target']  # 2=Home, 1=Draw, 0=Away

        max_prob = max(prob_h, prob_d, prob_a)

        # Confidence filter
        if max_prob <= 0.6:
            continue

        edge_threshold = 0.02

        # ---------------- HOME BET ----------------
        if prob_h > implied_h + edge_threshold:
            fraction = kelly_fraction(prob_h, odds_h)
            fraction = min(fraction, 0.05)

            stake = bankroll * fraction
            if stake <= 0:
                continue

            bankroll -= stake
            bets_placed += 1

            if actual_result == 2:
                bankroll += stake * odds_h
                bets_won += 1

        # ---------------- AWAY BET ----------------
        elif prob_a > implied_a + edge_threshold:
            fraction = kelly_fraction(prob_a, odds_a)
            fraction = min(fraction, 0.05)

            stake = bankroll * fraction
            if stake <= 0:
                continue

            bankroll -= stake
            bets_placed += 1

            if actual_result == 0:
                bankroll += stake * odds_a
                bets_won += 1

    # -------------------------------
    # 6. Final Results
    # -------------------------------
    roi = ((bankroll - starting_bankroll) / starting_bankroll) * 100

    results = {
        "metrics": metrics,
        "betting_simulation": {
            "starting_bankroll": starting_bankroll,
            "ending_bankroll": round(bankroll, 2),
            "total_profit": round(bankroll - starting_bankroll, 2),
            "bets_placed": bets_placed,
            "bets_won": bets_won,
            "win_rate": round((bets_won / bets_placed) * 100, 2) if bets_placed > 0 else 0,
            "roi_percentage": round(roi, 2)
        }
    }

    print("\n--- Backtest Results ---")
    print(json.dumps(results, indent=2))

    # Save results
    os.makedirs('data', exist_ok=True)

    with open('data/backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print("Saved model and backtest results.")


# -------------------------------
# Run
# -------------------------------
if __name__ == "__main__":
    run_backtest()
