import gzip

from chess_app.pgn_sources import download_pgn


def test_download_pgn(tmp_path):
    sample = b"[Event \"Test\"]\n\n1. e4 e5 1-0\n"
    gz_path = tmp_path / "sample.pgn.gz"
    with gzip.open(gz_path, 'wb') as f:
        f.write(sample)

    url = f"file://{gz_path}"
    out = tmp_path / "out.pgn"
    download_pgn(url, str(out))
    assert out.read_bytes() == sample
