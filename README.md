# Chess App

This is a chess application with a graphical user interface.

## Setup Instructions

### Prerequisites

*   Python 3.x
*   Git

### Installation

1.  **Download the repository:**

    Open your terminal or command prompt and use the following command to clone the repository to your local machine:

    ```bash
    git clone https://github.com/your-username/chess-app.git
    ```

    Replace `https://github.com/your-username/chess-app.git` with the actual URL of this repository.

2.  **Navigate to the project directory:**

    ```bash
    cd chess-app
    ```

3.  **Set up a Python virtual environment (recommended):**

    It's highly recommended to use a virtual environment to manage project-specific dependencies. This keeps your global Python installation clean.

    *   **Create a virtual environment (macOS/Linux):**
        ```bash
        python3 -m venv venv
        ```
    *   **Activate the virtual environment (macOS/Linux):**
        ```bash
        source venv/bin/activate
        ```
    For Windows, the commands are slightly different. Please refer to the official Python documentation for `venv`.

4.  **Install Python dependencies:**

The primary known dependency for the graphical interface is PySide6.

    Install it using pip:
    ```bash
    pip install PySide6
    ```
    Other dependencies might be identified as development progresses. For now, PySide6 is the essential one to get started.

### Quick Setup Scripts

For convenience the repository includes shell scripts that download the app and the Stockfish engine in one step.

* **Ubuntu/Linux:** `setup_chess_ubuntu.sh`
* **macOS:** `setup_chess_macos.sh`

Both scripts clone this repository, create a Python virtual environment, download a Stockfish binary and generate a `run_chess.sh` launcher. Edit the `APP_REPO_URL` variable inside the script to point to your fork or mirror, make the script executable and run it:

```bash
chmod +x setup_chess_ubuntu.sh
./setup_chess_ubuntu.sh
```

After the script finishes you can start the GUI with `./run_chess.sh` from the target directory.

### One-Click Install

To download and install the application in a single step you can execute the installer script directly from the repository:

```bash
curl -fsSL https://example.com/install_chess_app.sh | bash
```

Replace the URL above with the raw address of this repository's `install_chess_app.sh` if using a fork.

5.  **Configure the Stockfish Chess Engine (macOS):**

    This application uses the Stockfish chess engine for gameplay analysis and opponent moves. You need to have a Stockfish executable accessible to the application. You can download Stockfish from [https://stockfishchess.org/download/](https://stockfishchess.org/download/). Choose the appropriate version for your Mac (e.g., AVX2 or POPCNT).

    There are two primary ways to configure Stockfish:

    *   **Method 1: Using the `STOCKFISH_ENV_PATH` Environment Variable**

        You can tell the application exactly where to find your Stockfish executable by setting this environment variable.

        *   **For the current terminal session:**
            Open your terminal and run:
            ```bash
            export STOCKFISH_ENV_PATH=/path/to/your/stockfish
            ```
            **Note:** Replace `/path/to/your/stockfish` with the actual, full path to your Stockfish executable file (e.g., `/Users/yourname/Downloads/stockfish-16-mac-x86-64-avx2/stockfish`).

        *   **To set it permanently (recommended for convenience):**
            Add the `export` command to your shell's configuration file. If you are using Zsh (default on newer macOS versions), this is `~/.zshrc`. If you are using Bash, it's typically `~/.bash_profile` or `~/.bashrc`.
            For example, to add it to `~/.zshrc`:
            ```bash
            echo 'export STOCKFISH_ENV_PATH=/path/to/your/stockfish' >> ~/.zshrc
            source ~/.zshrc  # Apply the changes to the current session
            ```
            Remember to replace `/path/to/your/stockfish` with the actual path.

    *   **Method 2: Ensuring Stockfish is in the System `PATH`**

        If Stockfish is in a directory that's part of your system's `PATH` environment variable, the application should find it automatically.

        *   **Option A: Copy Stockfish to a standard `PATH` directory:**
            You can copy the Stockfish executable to a directory like `/usr/local/bin`.
            ```bash
            sudo cp /path/to/your/stockfish /usr/local/bin/stockfish
            ```
            Again, replace `/path/to/your/stockfish` with the actual path to the executable. You'll need administrator privileges (`sudo`) for this.

        *   **Option B: Add Stockfish's directory to your `PATH`:**
            If you prefer to keep the Stockfish executable where you downloaded it, you can add its containing directory to your `PATH`.
            For example, if Stockfish is in `/Users/yourname/Downloads/stockfish-16-mac-x86-64-avx2/`, you would add this directory to your `PATH`.
            Edit your `~/.zshrc` (or `~/.bash_profile`) and add a line like:
            ```bash
            export PATH="/path/to/your/stockfish_directory:$PATH"
            ```
            Replace `/path/to/your/stockfish_directory` with the path to the *directory* containing the Stockfish executable. Then, source the file (e.g., `source ~/.zshrc`).

    **Important:** After downloading Stockfish, ensure the executable has permission to run. You might need to use `chmod +x /path/to/your/stockfish`.

## Running the Application

Once you have completed all the setup steps:

1.  **Navigate to the project's root directory** (if you're not already there):
    ```bash
    cd path/to/chess-app
    ```
    (Replace `path/to/chess-app` with the actual path if you named the directory differently or are not in its parent directory). If you followed the previous steps, you might already be in this directory (`chess-app`).

2.  **Activate your virtual environment** (if you created one):
    ```bash
    source venv/bin/activate
    ```
    Remember to do this every time you open a new terminal session to work on the project.

3.  **Run the application:**
    ```bash
    python chess_app/main.py
    ```

This should launch the chess application's graphical user interface.

## Future Plans and Limitations

The project focuses on a local GUI that uses the Stockfish engine for
analysis.  Basic modules for online play, chat and tournament management are
included but remain minimal examples.  Full mobile support and advanced
network features would require substantial additional work.

Possible areas for future exploration include:

* Networked play over the internet or local wireless connections
* Chat integration between players
* Tournament brackets and multi‑player (for example 4‑player chess)
* Dedicated Android/iOS user interfaces

Contributions or forks implementing these ideas are welcome.

## PGN Database Tools

The repository includes simple helpers to work with large PGN databases.  The
`pgn_database.py` module can load games and filter them by ELO, opening name and
winner color.  The `pgn_sources.py` module provides a `download_pgn()` function
to download public PGN archives (for example from FIDE) in a single call.

```python
from chess_app.pgn_sources import download_pgn
from chess_app.pgn_database import load_games, filter_games

pgn_file = download_pgn("https://example.com/fide_games_2024.pgn.gz", "games.pgn")
all_games = list(load_games(pgn_file))
strong_games = filter_games(all_games, min_elo=2500)
```

These utilities are optional but demonstrate how to collect and query official
game archives.
