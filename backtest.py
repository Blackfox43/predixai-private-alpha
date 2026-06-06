import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss

from betting_engine_v6 import BettingEngineV6
from data_pipeline import build_dataset
from feature_engineering_v6 import FeatureEngineeringV6
from model_v6 import V6Model

DATA_PATH = Path("data/historical_matches.csv")
RESULTS_PATH = Path("data/backtest_results.json")
FEATURE_COLUMNS = ["home_elo", "away_elo", "elo_diff", "home_form", "away_form", "form_diff"]


def _first_existing_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str:
    for name in candidates:
        if name in df.columns:
            return name
    raise KeyError(f"missing required column; expected one of {candidates}")


def load_dataset() -> pd.DataFrame:
    if not DATA_PATH.exists():
        print("Dataset missing — rebuilding...")
        df = build_dataset()
    else:
        df = pd.read_csv(DATA_PATH)

    required = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"historical dataset is missing columns: {missing}")

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"])
    return df.sort_values("Date").reset_index(drop=True)


def run_backtest(window: int = 600, retrain_interval: int = 200):
    print("Starting CLEAN V6 SYSTEM...")
    raw_df = load_dataset()

    odds_cols = {
        "home": _first_existing_column(raw_df, ("B365H", "HomeOdds")),
        "draw": _first_existing_column(raw_df, ("B365D", "DrawOdds")),
        "away": _first_existing_column(raw_df, ("B365A", "AwayOdds")),
    }

    fe = FeatureEngineeringV6()
    df = fe.transform(raw_df).dropna(subset=FEATURE_COLUMNS + list(odds_cols.values()) + ["result"])
    df = df.reset_index(drop=True)

    if len(df) <= window:
        raise ValueError(f"not enough rows for window={window}; only {len(df)} usable rows")

    model = V6Model()
    engine = BettingEngineV6()
    all_probs = []
    all_y = []

    print("Running walk-forward backtest...")
    for i in range(window, len(df)):
        train = df.iloc[:i]
        test = df.iloc[i : i + 1]

        if (i == window) or ((i - window) % retrain_interval == 0):
            model.train(train[FEATURE_COLUMNS].to_numpy(dtype=float), train["result"].to_numpy(dtype=int))

        probs = model.predict_proba(test[FEATURE_COLUMNS].to_numpy(dtype=float))[0]
        actual = int(test["result"].iloc[0])  # 0=home, 1=draw, 2=away
        odds = np.array([
            float(test[odds_cols["home"]].iloc[0]),
            float(test[odds_cols["draw"]].iloc[0]),
            float(test[odds_cols["away"]].iloc[0]),
        ])

        all_probs.append(probs)
        all_y.append(actual)
        engine.settle(engine.evaluate(probs, odds), actual, odds)

    probs_arr = np.vstack(all_probs)
    y_arr = np.asarray(all_y, dtype=int)
    pred_arr = np.argmax(probs_arr, axis=1)
    one_hot = np.eye(3)[y_arr]

    results = {
        "metrics": {
            "log_loss": round(float(log_loss(y_arr, probs_arr, labels=[0, 1, 2])), 6),
            "brier_score": round(float(np.mean(np.sum((probs_arr - one_hot) ** 2, axis=1))), 6),
            "accuracy": round(float(accuracy_score(y_arr, pred_arr)), 6),
        },
        "betting_simulation": engine.report(),
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    run_backtest()
