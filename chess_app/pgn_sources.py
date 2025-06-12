"""Utilities for downloading PGN data from online sources."""

import gzip
from pathlib import Path
from urllib.request import urlopen


def download_pgn(url: str, dest_path: str) -> str:
    """Download a PGN file from a URL. Supports optional gzip compression."""
    dest = Path(dest_path)
    if url.endswith('.gz'):
        with urlopen(url) as response, gzip.open(response) as gz:
            dest.write_bytes(gz.read())
    else:
        with urlopen(url) as response:
            dest.write_bytes(response.read())
    return str(dest)
