import pandas as pd

K = 20
INITIAL_RATING = 1500

def expected_score(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

def update_elo(rating_a, rating_b, result):
    # result: 1 = win, 0.5 = draw, 0 = loss
    expected_a = expected_score(rating_a, rating_b)
    new_a = rating_a + K * (result - expected_a)
    return new_a

def add_elo_features(df):
    ratings = {}

    elo_home = []
    elo_away = []

    for _, row in df.iterrows():
        home = row['HomeTeam']
        away = row['AwayTeam']

        ratings.setdefault(home, INITIAL_RATING)
        ratings.setdefault(away, INITIAL_RATING)

        elo_home.append(ratings[home])
        elo_away.append(ratings[away])

        # Determine result
        if 'FTR' in row:
            if row['FTR'] == 'H':
                home_result, away_result = 1, 0
            elif row['FTR'] == 'A':
                home_result, away_result = 0, 1
            else:
                home_result, away_result = 0.5, 0.5
        elif 'FTHG' in row and 'FTAG' in row:
            if row['FTHG'] > row['FTAG']:
                home_result, away_result = 1, 0
            elif row['FTHG'] < row['FTAG']:
                home_result, away_result = 0, 1
            else:
                home_result, away_result = 0.5, 0.5
        else:
            home_result, away_result = 0.5, 0.5 # Default if no result

        new_home = update_elo(ratings[home], ratings[away], home_result)
        new_away = update_elo(ratings[away], ratings[home], away_result)

        ratings[home] = new_home
        ratings[away] = new_away

    df['elo_home'] = elo_home
    df['elo_away'] = elo_away
    df['elo_diff'] = df['elo_home'] - df['elo_away']

    return df
