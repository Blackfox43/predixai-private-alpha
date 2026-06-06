import pandas as pd
import os

def download_historical_data():
    """
    Downloads real historical match data from football-data.co.uk.
    This provides actual results, match stats (shots, corners, fouls), and bookmaker odds.
    """
    print("Downloading historical data...")
    # Premier League data for the last 3 completed seasons
    urls = [
        "https://www.football-data.co.uk/mmz4281/2122/E0.csv",
        "https://www.football-data.co.uk/mmz4281/2223/E0.csv",
        "https://www.football-data.co.uk/mmz4281/2324/E0.csv"
    ]
    
    dfs = []
    for url in urls:
        try:
            df = pd.read_csv(url)
            dfs.append(df)
            print(f"Successfully downloaded: {url}")
        except Exception as e:
            print(f"Failed to download {url}: {e}")
            
    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
        
        # Standardize Date format
        combined['Date'] = pd.to_datetime(combined['Date'], format='%d/%m/%Y', errors='coerce')
        
        # Drop rows with missing essential data
        combined = combined.dropna(subset=['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG'])
        
        # Sort chronologically
        combined = combined.sort_values('Date').reset_index(drop=True)
        
        os.makedirs('data', exist_ok=True)
        combined.to_csv('data/historical_matches.csv', index=False)
        print(f"Saved {len(combined)} matches to data/historical_matches.csv")
        return combined
    return None

if __name__ == "__main__":
    download_historical_data()
