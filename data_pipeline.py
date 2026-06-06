import pandas as pd
import os

def build_dataset():
    urls = [
        "https://www.football-data.co.uk/mmz4281/2122/E0.csv",
        "https://www.football-data.co.uk/mmz4281/2223/E0.csv",
        "https://www.football-data.co.uk/mmz4281/2324/E0.csv",
    ]

    dfs = [pd.read_csv(url) for url in urls]
    df = pd.concat(dfs, ignore_index=True)

    os.makedirs("data", exist_ok=True)
    df.to_csv("data/historical_matches.csv", index=False)

    return df
