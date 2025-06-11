from chess_app.tournament import schedule_round_robin, Tournament


def test_round_robin_pairings():
    players = ["A", "B", "C"]
    pairings = schedule_round_robin(players)
    assert ("A", "B") in pairings
    assert ("A", "C") in pairings
    assert ("B", "C") in pairings


def test_tournament_standings():
    t = Tournament(["A", "B"])
    t.record_result("A", "B", "1-0")
    scores = t.standings()
    assert scores["A"] == 1
    assert scores["B"] == 0

