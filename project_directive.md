# Project Directive

This repository hosts a cross‑platform chess application with optional language model integration. The code should remain easy to install on macOS and Ubuntu.

## Goals

- Provide a one‑command installer that automatically fetches the latest Stockfish engine.
- Keep the core application offline and self‑contained.
- Optional Gemma 3n model support for natural language features.
- Maintain unit tests to validate engine behavior and basic GUI logic.
- Keep external dependencies minimal: primarily PySide6 for the GUI.

## Contribution Guidelines

- Follow Python best practices and keep scripts POSIX compatible when possible.
- Document new features in the README.
- Run `pytest -q` before committing changes.

Future expansions may include online play, tournament management and mobile interfaces. These are out of scope for now but contributions exploring them are welcome.
