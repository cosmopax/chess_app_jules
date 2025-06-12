from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class MatchResult:
    player1: str
    player2: str
    result: str  # "1-0", "0-1", or "1/2-1/2"


def schedule_round_robin(players: List[str]) -> List[Tuple[str, str]]:
    """Return pairings for a single round-robin."""
    pairings = []
    n = len(players)
    for i in range(n):
        for j in range(i + 1, n):
            pairings.append((players[i], players[j]))
    return pairings


class Tournament:
    def __init__(self, players: List[str]):
        self.players = players
        self.results: Dict[Tuple[str, str], str] = {}
        self.pairings = schedule_round_robin(players)

    def record_result(self, player1: str, player2: str, result: str) -> None:
        if (player1, player2) in self.pairings:
            self.results[(player1, player2)] = result
        elif (player2, player1) in self.pairings:
            self.results[(player2, player1)] = result

    def standings(self) -> Dict[str, float]:
        scores = {p: 0.0 for p in self.players}
        for (p1, p2), result in self.results.items():
            if result == "1-0":
                scores[p1] += 1
            elif result == "0-1":
                scores[p2] += 1
            else:
                scores[p1] += 0.5
                scores[p2] += 0.5
        return scores

