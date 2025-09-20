from datetime import date

from chess_app import srs


def test_sm2_first_fail():
    item = srs.SRSItem()
    today = date(2025, 1, 1)
    srs.update(item, quality=2, today=today)
    assert item.repetitions == 0
    assert item.interval == 1
    assert item.due == today + srs.timedelta(days=1)


def test_sm2_successive_reviews():
    item = srs.SRSItem()
    today = date(2025, 1, 1)
    srs.update(item, quality=4, today=today)
    assert item.repetitions == 1
    assert item.interval == 1
    first_due = item.due
    srs.update(item, quality=5, today=today)
    assert item.repetitions == 2
    assert item.interval == 6
    assert item.due == today + srs.timedelta(days=6)
    assert item.due != first_due


def test_due_items():
    today = date(2025, 1, 1)
    items = [
        srs.SRSItem(due=today - srs.timedelta(days=1)),
        srs.SRSItem(due=today),
        srs.SRSItem(due=today + srs.timedelta(days=1)),
    ]
    due = srs.due_items(items, today=today)
    assert len(due) == 2


def test_load_and_save_items(tmp_path):
    items = [srs.SRSItem(easiness=2.5, interval=1, repetitions=1, due=date(2025, 1, 2))]
    file_path = tmp_path / "items.json"
    srs.save_items(items, file_path)
    loaded = srs.load_items(file_path)
    assert len(loaded) == 1
    assert loaded[0].due == items[0].due
