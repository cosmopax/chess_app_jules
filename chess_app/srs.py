"""Spaced repetition scheduling using the SM-2 algorithm."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, List
import json


@dataclass
class SRSItem:
    """Represents a training item for spaced repetition."""

    easiness: float = 2.5
    interval: int = 0
    repetitions: int = 0
    due: date = date.today()


def update(item: SRSItem, quality: int, today: date | None = None) -> SRSItem:
    """Update ``item`` according to the SM-2 algorithm.

    Parameters
    ----------
    item:
        The item to update.
    quality:
        Quality of recall on a 0-5 scale.
    today:
        The reference date for scheduling. Defaults to ``date.today()``.

    Returns
    -------
    SRSItem
        The updated item.
    """

    if today is None:
        today = date.today()

    if quality < 3:
        item.repetitions = 0
        item.interval = 1
    else:
        if item.repetitions == 0:
            item.interval = 1
        elif item.repetitions == 1:
            item.interval = 6
        else:
            item.interval = round(item.interval * item.easiness)
        item.repetitions += 1
        item.easiness += 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
        if item.easiness < 1.3:
            item.easiness = 1.3

    item.due = today + timedelta(days=item.interval)
    return item


def due_items(items: Iterable[SRSItem], today: date | None = None) -> List[SRSItem]:
    """Return items whose due date is today or earlier."""
    if today is None:
        today = date.today()
    return [item for item in items if item.due <= today]


def save_items(items: Iterable[SRSItem], path: str | Path) -> None:
    """Save items to *path* in JSON format."""
    data = [asdict(item) | {"due": item.due.isoformat()} for item in items]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def load_items(path: str | Path) -> List[SRSItem]:
    """Load items previously saved with :func:`save_items`."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    items = []
    for entry in raw:
        due = date.fromisoformat(entry["due"])
        item = SRSItem(
            easiness=entry.get("easiness", 2.5),
            interval=entry.get("interval", 0),
            repetitions=entry.get("repetitions", 0),
            due=due,
        )
        items.append(item)
    return items
