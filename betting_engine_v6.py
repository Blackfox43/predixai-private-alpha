import math
from typing import Dict, Iterable, Optional

import numpy as np


class BettingEngineV6:
    """Stateful flat-fraction betting simulator for probabilities ordered H/D/A."""

    def __init__(self, bankroll: float = 1000.0, stake_fraction: float = 0.03, min_edge: float = 0.005):
        if bankroll <= 0:
            raise ValueError("bankroll must be positive")
        if not 0 < stake_fraction <= 1:
            raise ValueError("stake_fraction must be in (0, 1]")
        self.bankroll = float(bankroll)
        self.initial = float(bankroll)
        self.stake_fraction = float(stake_fraction)
        self.min_edge = float(min_edge)
        self.bets = 0
        self.wins = 0

    @staticmethod
    def _clean_vector(values: Iterable[float], *, name: str) -> np.ndarray:
        arr = np.asarray(list(values), dtype=float)
        if arr.shape != (3,) or not np.all(np.isfinite(arr)):
            raise ValueError(f"{name} must contain exactly three finite values")
        return arr

    @staticmethod
    def edge(probability: float, decimal_odds: float) -> float:
        if decimal_odds <= 1:
            return -math.inf  # Invalid/unprofitable odds should never be selected.
        return probability - (1.0 / decimal_odds)

    def evaluate(self, probs: Iterable[float], odds: Iterable[float]) -> Dict[str, Optional[float]]:
        probs_arr = self._clean_vector(probs, name="probs")
        odds_arr = self._clean_vector(odds, name="odds")

        if np.any(probs_arr < 0):
            raise ValueError("probabilities cannot be negative")
        prob_sum = probs_arr.sum()
        if prob_sum <= 0:
            return {"bet": None}
        probs_arr = probs_arr / prob_sum  # Avoid bad model output creating oversized stakes.

        edges = np.array([self.edge(p, o) for p, o in zip(probs_arr, odds_arr)])
        best = int(np.argmax(edges))
        best_edge = float(edges[best])

        if best_edge < self.min_edge or self.bankroll <= 0:
            return {"bet": None}

        stake = min(self.bankroll * self.stake_fraction, self.bankroll)
        return {"bet": best, "stake": stake, "edge": best_edge}

    def settle(self, decision: Dict[str, Optional[float]], result: int, odds: Iterable[float]) -> None:
        bet = decision.get("bet")
        if bet is None:
            return
        if bet not in (0, 1, 2) or result not in (0, 1, 2):
            raise ValueError("bet and result must use 0=home, 1=draw, 2=away")

        odds_arr = self._clean_vector(odds, name="odds")
        stake = min(float(decision.get("stake") or 0.0), self.bankroll)
        if stake <= 0:
            return

        self.bets += 1
        if bet == result:
            self.bankroll += stake * (float(odds_arr[bet]) - 1.0)
            self.wins += 1
        else:
            self.bankroll -= stake

    def report(self):
        profit = self.bankroll - self.initial
        return {
            "starting_bankroll": round(self.initial, 2),
            "ending_bankroll": round(self.bankroll, 2),
            "total_profit": round(profit, 2),
            "bets_placed": self.bets,
            "bets_won": self.wins,
            "win_rate": round((self.wins / self.bets * 100) if self.bets else 0.0, 2),
            "roi_percentage": round((profit / self.initial * 100), 2),
        }
