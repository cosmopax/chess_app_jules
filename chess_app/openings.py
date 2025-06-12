"""Utilities for retrieving opening information.

This module extends the local opening detection provided by ``python-chess``
with the ability to query the public Lichess opening explorer API.  The API
contains a large database of master and online games and is ideal for studying
opening lines and popular continuations.

The helper ``fetch_lichess_moves`` returns the most common moves from the given
position.  Network failures are handled gracefully by returning ``None``.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

import chess

logger = logging.getLogger(__name__)


LICHESS_API_URL = "https://explorer.lichess.ovh/masters"


def fetch_lichess_moves(board: chess.Board, max_moves: int = 8) -> list[dict] | None:
    """Return opening move statistics from Lichess for ``board``.

    Parameters
    ----------
    board:
        The board position to query.
    max_moves:
        Limit the number of moves returned by the API.

    Returns
    -------
    list[dict] | None
        ``list`` of move dictionaries as returned by the API, or ``None`` if the
        query fails.
    """

    fen = board.fen()
    params = urllib.parse.urlencode({"fen": fen, "moves": str(max_moves)})
    url = f"{LICHESS_API_URL}?{params}"

    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("moves")
    except Exception as exc:  # pragma: no cover - network failures
        logger.debug("Lichess opening lookup failed: %s", exc)
        return None

