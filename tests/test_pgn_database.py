import textwrap
from chess_app.pgn_database import load_games, filter_games


def test_filter_games(tmp_path):
    sample_pgn = textwrap.dedent(
        """
        [Event "Test"]
        [Site "Test"]
        [Date "2020.01.01"]
        [Round "1"]
        [White "A"]
        [Black "B"]
        [Result "1-0"]
        [WhiteElo "2400"]
        [BlackElo "2300"]
        [Opening "Sicilian Defense"]

        1. e4 c5 2. Nf3 d6 1-0

        [Event "Test"]
        [Site "Test"]
        [Date "2020.01.02"]
        [Round "2"]
        [White "C"]
        [Black "D"]
        [Result "0-1"]
        [WhiteElo "2100"]
        [BlackElo "2500"]
        [Opening "French Defense"]

        1. e4 e6 2. d4 d5 0-1
        """
    )
    pgn_file = tmp_path / "games.pgn"
    pgn_file.write_text(sample_pgn)
    games = list(load_games(str(pgn_file)))
    assert len(games) == 2
    filt = filter_games(games, min_elo=2200, winner_color="white")
    assert len(filt) == 1
    assert filt[0].headers["Opening"] == "Sicilian Defense"

