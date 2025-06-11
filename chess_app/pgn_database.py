from dataclasses import dataclass
from typing import Iterable, List, Optional, Dict
import re


@dataclass
class PGNGame:
    headers: Dict[str, str]
    moves: str


def load_games(pgn_path: str) -> Iterable[PGNGame]:
    """Yield minimal PGNGame objects from a PGN file."""
    header_re = re.compile(r"^\[(\w+)\s+\"(.*)\"\]$")
    with open(pgn_path, "r", encoding="utf-8", errors="ignore") as f:
        headers: Dict[str, str] = {}
        moves: List[str] = []
        for line in f:
            line = line.rstrip()
            if not line:
                if headers:
                    yield PGNGame(headers=headers, moves="\n".join(moves))
                    headers = {}
                    moves = []
                continue
            if line.startswith("[") and line.endswith("]"):
                m = header_re.match(line)
                if m:
                    headers[m.group(1)] = m.group(2)
            else:
                moves.append(line)
        if headers:
            yield PGNGame(headers=headers, moves="\n".join(moves))


def filter_games(
    games: Iterable[PGNGame],
    min_elo: Optional[int] = None,
    max_elo: Optional[int] = None,
    opening: Optional[str] = None,
    winner_color: Optional[str] = None,
) -> List[PGNGame]:
    """Filter games by ELO range, opening name and winning color."""
    filtered: List[PGNGame] = []
    winner_color = winner_color.lower() if winner_color else None
    for game in games:
        white_elo = int(game.headers.get("WhiteElo", "0") or 0)
        black_elo = int(game.headers.get("BlackElo", "0") or 0)
        if min_elo and white_elo < min_elo and black_elo < min_elo:
            continue
        if max_elo and white_elo > max_elo and black_elo > max_elo:
            continue
        if opening and game.headers.get("Opening") != opening:
            continue
        result = game.headers.get("Result")
        if winner_color == "white" and result != "1-0":
            continue
        if winner_color == "black" and result != "0-1":
            continue
        filtered.append(game)
    return filtered

