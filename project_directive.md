# Project Directive

This repository hosts a cross‑platform chess application with an integrated **Openings Mentor** and optional language model features. The code should remain easy to install on macOS and Ubuntu and work offline by default.

## Goals

- Provide a **one‑command installer** (`install_chess_app.sh`) that detects the OS, creates a virtual environment, installs dependencies, and fetches the newest Stockfish engine.
- Keep the core application offline and self‑contained, with optional online components.
- Integrate an **Openings Mentor** module with:
  - A local SQLite database of PGN openings annotated with ECO codes, names, SAN moves, and basic statistics.
  - Interactive opening tree visualisation and navigation using PySide6 widgets.
  - Spaced‑repetition training (SM‑2) for move recall, position completion and repertoire drills.
  - Implemented in `chess_app.srs` with unit tests. Items can be persisted via `save_items` and reloaded with `load_items`.
  - Multiple drill modes offering incremental hints and performance analytics.
- Support optional Gemma 3n model download for natural language features and chat mentoring.
- Provide context‑aware LLM chat integration via the Jules.Google/Codex client informed by current FEN, Stockfish evaluation and opening metadata.
- Maintain unit tests (`pytest -q`) and code style checks (`flake8`, `black --check`).
- Minimise external dependencies: primarily PySide6, python‑chess, SQLAlchemy and the LLM client library.

## Architecture Overview

- **GUI:** PySide6 with modular widgets for board display, opening trees, drill interfaces and chat panels.
- **Chess Engine:** Stockfish controlled via the python‑chess UCI wrapper and bundled by the installer.
- **Database:** SQLite accessed with SQLAlchemy for repertoires, games, ECO codes and SRS scheduling.
- **LLM:** Jules.Google/Codex client for natural language queries and adaptive tutoring.

## Installation & Setup

- Run:

  ```bash
  bash <(curl -fsSL https://raw.githubusercontent.com/cosmopax/chess_app_jules/main/install_chess_app.sh)
  ```
  Use `-y` to install with default options non‑interactively.

  The installer fetches the latest Stockfish release and prompts for an optional Gemma 3n download.
- The scripts `setup_chess_ubuntu.sh` and `setup_chess_macos.sh` remain POSIX‑compatible for manual use.
- Set `STOCKFISH_ENV_PATH` or ensure the Stockfish executable is in `PATH` for engine discovery.

## Contribution Guidelines

- Follow Python best practices; keep shell scripts POSIX compatible.
- Document new features and update this directive file.
- Write unit tests for new functionality and ensure `pytest -q` passes.
- Enforce code style with `flake8` and `black --check`.
- Adhere to semantic versioning for releases.

## Testing & CI/CD

- Automated test suite covers PGN parsing, engine integration, training algorithms, GUI workflows and LLM interactions.
- CI pipeline enforces tests, style checks and builds on both macOS and Ubuntu runners.

## Future Scope

- Online play, tournament management and peer‑to‑peer match‑making.
- Mobile interfaces (PySide6/QML or standalone Electron/React Native builds).
- Cloud sync and cross‑device repertoire sharing.
- Enhanced analytics dashboard and community opening database integration.

