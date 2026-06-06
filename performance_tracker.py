import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Iterable, Optional


class PerformanceTracker:
    def __init__(self, db_path: str = "data/tracker.db"):
        directory = os.path.dirname(db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path, timeout=10)

    def _init_db(self):
        with closing(self._connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    home_team TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    prob_home REAL NOT NULL,
                    prob_draw REAL NOT NULL,
                    prob_away REAL NOT NULL,
                    odds_home REAL,
                    odds_draw REAL,
                    odds_away REAL,
                    predicted_outcome TEXT NOT NULL,
                    actual_outcome TEXT,
                    profit REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_predictions_match_id ON predictions(match_id)")
            conn.commit()

    @staticmethod
    def _validate_triplet(values: Iterable[float], name: str):
        values = list(values)
        if len(values) != 3:
            raise ValueError(f"{name} must contain [home, draw, away]")
        return [float(v) for v in values]

    def log_prediction(self, match_id: str, date: str, home: str, away: str, probs, odds: Optional[Iterable[float]] = None):
        """Log/update a prediction. Probabilities are ordered [home, draw, away]."""
        prob_h, prob_d, prob_a = self._validate_triplet(probs, "probs")
        odds_h, odds_d, odds_a = self._validate_triplet(odds, "odds") if odds else (None, None, None)
        outcomes = [("H", prob_h), ("D", prob_d), ("A", prob_a)]
        predicted_outcome = max(outcomes, key=lambda item: item[1])[0]

        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO predictions
                    (match_id, date, home_team, away_team, prob_home, prob_draw, prob_away,
                     odds_home, odds_draw, odds_away, predicted_outcome, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(match_id) DO UPDATE SET
                    date=excluded.date,
                    home_team=excluded.home_team,
                    away_team=excluded.away_team,
                    prob_home=excluded.prob_home,
                    prob_draw=excluded.prob_draw,
                    prob_away=excluded.prob_away,
                    odds_home=excluded.odds_home,
                    odds_draw=excluded.odds_draw,
                    odds_away=excluded.odds_away,
                    predicted_outcome=excluded.predicted_outcome
                """,
                (
                    match_id,
                    date,
                    home,
                    away,
                    prob_h,
                    prob_d,
                    prob_a,
                    odds_h,
                    odds_d,
                    odds_a,
                    predicted_outcome,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def resolve_match(self, match_id: str, actual_outcome: str, stake: float = 10.0):
        if actual_outcome not in {"H", "D", "A"}:
            raise ValueError("actual_outcome must be one of H, D, A")

        with closing(self._connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT predicted_outcome, odds_home, odds_draw, odds_away FROM predictions WHERE match_id = ?",
                (match_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError(f"prediction not found for match_id={match_id}")

            predicted_outcome, odds_h, odds_d, odds_a = row
            profit = -float(stake)
            if predicted_outcome == actual_outcome:
                odds_by_outcome = {"H": odds_h, "D": odds_d, "A": odds_a}
                selected_odds = odds_by_outcome[actual_outcome]
                if selected_odds:
                    profit = float(stake) * (float(selected_odds) - 1.0)

            cursor.execute(
                "UPDATE predictions SET actual_outcome = ?, profit = ? WHERE match_id = ?",
                (actual_outcome, profit, match_id),
            )
            conn.commit()

    def get_performance_stats(self, limit: int = 10):
        with closing(self._connect()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM predictions WHERE actual_outcome IS NOT NULL")
            total_resolved = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM predictions WHERE actual_outcome IS NOT NULL AND actual_outcome = predicted_outcome"
            )
            total_correct = cursor.fetchone()[0]
            cursor.execute("SELECT COALESCE(SUM(profit), 0.0) FROM predictions WHERE actual_outcome IS NOT NULL")
            total_profit = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT home_team || ' vs ' || away_team, predicted_outcome, actual_outcome, profit
                FROM predictions
                WHERE actual_outcome IS NOT NULL
                ORDER BY date DESC
                LIMIT ?
                """,
                (limit,),
            )
            recent = [
                {"match": match, "predicted": predicted, "actual": actual, "profit": round(float(profit), 2)}
                for match, predicted, actual, profit in cursor.fetchall()
            ]

        return {
            "total_tracked": total_resolved,
            "accuracy": round((total_correct / total_resolved * 100) if total_resolved else 0.0, 2),
            "total_profit": round(float(total_profit), 2),
            "recent_matches": recent,
        }


if __name__ == "__main__":
    tracker = PerformanceTracker()
    print(tracker.get_performance_stats())
