import pandas as pd
import numpy as np

class FeatureEngineeringV6:
    """
    CLEAN V6 FEATURES:
    - Elo ratings
    - rolling form
    - no leakage
    """

    def __init__(self, k=20):
        self.k = k
        self.elo = {}

    def get_elo(self, team):
        return self.elo.get(team, 1500)

    def expected(self, a, b):
        return 1 / (1 + 10 ** ((b - a) / 400))

    def update_elo(self, home, away, result):
        h = self.get_elo(home)
        a = self.get_elo(away)

        eh = self.expected(h, a)
        ea = 1 - eh

        if result == 0:
            sh, sa = 1, 0
        elif result == 2:
            sh, sa = 0, 1
        else:
            sh, sa = 0.5, 0.5

        self.elo[home] = h + self.k * (sh - eh)
        self.elo[away] = a + self.k * (sa - ea)

    def transform(self, df):
        required = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"}
        missing = sorted(required - set(df.columns))
        if missing:
            raise ValueError(f"missing required columns: {missing}")

        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
        df = df.dropna(subset=["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"])
        df = df.sort_values("Date").reset_index(drop=True)

        def result(row):
            if row["FTHG"] > row["FTAG"]:
                return 0
            elif row["FTHG"] < row["FTAG"]:
                return 2
            return 1

        df["result"] = df.apply(result, axis=1)

        home_elo, away_elo = [], []

        home_form_map = {}
        away_form_map = {}

        home_form, away_form = [], []

        for _, row in df.iterrows():
            h, a = row["HomeTeam"], row["AwayTeam"]

            home_elo.append(self.get_elo(h))
            away_elo.append(self.get_elo(a))

            hf = home_form_map.get(h, [])
            af = away_form_map.get(a, [])

            home_form.append(np.mean(hf) if len(hf) > 0 else 0.5)
            away_form.append(np.mean(af) if len(af) > 0 else 0.5)

            r = row["result"]

            home_form_map.setdefault(h, []).append(1 if r == 0 else 0)
            away_form_map.setdefault(a, []).append(1 if r == 2 else 0)

            if len(home_form_map[h]) > 5:
                home_form_map[h].pop(0)
            if len(away_form_map[a]) > 5:
                away_form_map[a].pop(0)

            self.update_elo(h, a, r)

        df["home_elo"] = home_elo
        df["away_elo"] = away_elo
        df["elo_diff"] = df["home_elo"] - df["away_elo"]

        df["home_form"] = home_form
        df["away_form"] = away_form
        df["form_diff"] = df["home_form"] - df["away_form"]

        return df
