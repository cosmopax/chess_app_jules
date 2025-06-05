#!/bin/bash
set -e

# --- Preamble & Definitions ---
TARGET_DIR="/home/cosmopax/Desktop/chess_jules"
APP_REPO_URL="<YOUR_CHESS_APP_REPO_URL_HERE>" # IMPORTANT: Replace this URL!
APP_DIR_NAME="chess-app"
STOCKFISH_DOWNLOAD_URL="https://stockfishchess.org/files/stockfish-16.1-linux-x86-64.tar.gz"
STOCKFISH_INTERNAL_EXEC_NAME="stockfish_binary" # Renamed executable inside our stockfish_engine dir

echo "--- Chess App Setup Script for Ubuntu ---"
echo "Target directory: $TARGET_DIR"
echo "App Repository URL: $APP_REPO_URL"
echo "Stockfish Download URL: $STOCKFISH_DOWNLOAD_URL"
echo ""

# --- System Dependencies ---
echo "--- Checking and Installing System Dependencies ---"
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip wget tar
echo "System dependencies checked/installed."
echo ""

# --- Target Directory ---
echo "--- Preparing Target Directory ---"
mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"
echo "Changed directory to $TARGET_DIR"
echo ""

# --- Chess App Repository (Clone or Update) ---
echo "--- Setting up Chess Application Repository ---"
APP_PATH="$TARGET_DIR/$APP_DIR_NAME"
if [ -d "$APP_PATH" ]; then
    echo "Application directory '$APP_PATH' already exists. Attempting to update..."
    cd "$APP_PATH"
    git pull
    cd "$TARGET_DIR"
    echo "Application repository updated."
else
    echo "Cloning application repository from '$APP_REPO_URL' into '$APP_DIR_NAME'..."
    git clone "$APP_REPO_URL" "$APP_DIR_NAME"
    echo "Application repository cloned."
fi
echo ""

# --- Python Virtual Environment & Dependencies ---
echo "--- Setting up Python Virtual Environment and Dependencies ---"
cd "$APP_PATH"
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    echo "Virtual environment created."
else
    echo "Virtual environment 'venv' already exists."
fi

echo "Installing PySide6 into the virtual environment..."
venv/bin/pip install PySide6
echo "PySide6 installation complete."
cd "$TARGET_DIR"
echo ""

# --- Stockfish Setup/Update ---
echo "--- Setting up/Updating Stockfish Chess Engine ---"
STOCKFISH_DIR="$TARGET_DIR/stockfish_engine"
mkdir -p "$STOCKFISH_DIR"
cd "$STOCKFISH_DIR"

echo "Removing old Stockfish version if any..."
rm -rf ./* # Clear out the directory before downloading new version

echo "Downloading Stockfish from $STOCKFISH_DOWNLOAD_URL..."
if wget -O stockfish_archive.tar.gz "$STOCKFISH_DOWNLOAD_URL"; then
    echo "Stockfish archive downloaded."
    echo "Extracting Stockfish..."
    # Attempt to extract, stripping the top-level directory if present
    # The find command below will look for the actual binary
    if tar -xvzf stockfish_archive.tar.gz --strip-components=1; then
        echo "Stockfish extracted."

        # Search for the main Stockfish executable.
        # Prioritize common names. Exclude text/doc files.
        FOUND_EXEC=$(find . -maxdepth 1 -type f \( -name "stockfish" -o -name "stockfish-*" -o -name "Stockfish" \) ! -name "*.md" ! -name "*.txt" ! -name "*.tar.gz" -print -quit)

        if [ -n "$FOUND_EXEC" ] && [ -f "$FOUND_EXEC" ]; then
            echo "Found Stockfish executable: $FOUND_EXEC"
            mv "$FOUND_EXEC" "$STOCKFISH_INTERNAL_EXEC_NAME"
            chmod +x "$STOCKFISH_INTERNAL_EXEC_NAME"
            echo "Stockfish setup complete. Executable: $STOCKFISH_DIR/$STOCKFISH_INTERNAL_EXEC_NAME"
        else
            echo "Error: Could not find the Stockfish executable after extraction."
            echo "Please check the archive structure at $STOCKFISH_DOWNLOAD_URL or the extraction process."
            echo "The downloaded archive stockfish_archive.tar.gz is still in $STOCKFISH_DIR for inspection."
        fi
    else
        echo "Error: Failed to extract Stockfish archive. The archive might be corrupted or the structure unexpected."
        echo "The downloaded archive stockfish_archive.tar.gz is still in $STOCKFISH_DIR for inspection."
    fi
else
    echo "Error: wget failed to download Stockfish from $STOCKFISH_DOWNLOAD_URL."
    echo "Skipping further Stockfish processing for this run."
fi
cd "$TARGET_DIR"
echo ""

# --- Create Launcher Script (run_chess.sh) ---
echo "--- Creating Launcher Script (run_chess.sh) ---"
LAUNCHER_SCRIPT_PATH="$TARGET_DIR/run_chess.sh"

# Using a heredoc for the launcher script content
cat > "$LAUNCHER_SCRIPT_PATH" << EOL
#!/bin/bash
# Launcher for the Chess App
set -e

echo "Changing directory to script location: \$(dirname "\$0")"
cd "\$(dirname "\$0")" # Ensures script runs reliably from any location

TARGET_DIR_BASE="\$PWD" # Should be $TARGET_DIR
APP_DIR_NAME_LAUNCHER="$APP_DIR_NAME" # Must match APP_DIR_NAME from setup
APP_PATH_LAUNCHER="\$TARGET_DIR_BASE/\$APP_DIR_NAME_LAUNCHER"
STOCKFISH_INTERNAL_EXEC_NAME_LAUNCHER="$STOCKFISH_INTERNAL_EXEC_NAME" # Must match from setup
STOCKFISH_EXEC_PATH_LAUNCHER="\$TARGET_DIR_BASE/stockfish_engine/\$STOCKFISH_INTERNAL_EXEC_NAME_LAUNCHER"

echo "Activating Python virtual environment from \$APP_PATH_LAUNCHER/venv..."
if [ -f "\$APP_PATH_LAUNCHER/venv/bin/activate" ]; then
    source "\$APP_PATH_LAUNCHER/venv/bin/activate"
else
    echo "Error: Virtual environment not found at \$APP_PATH_LAUNCHER/venv."
    echo "Please run the setup script (setup_chess_ubuntu.sh) again."
    exit 1
fi

echo "Setting STOCKFISH_ENV_PATH to \$STOCKFISH_EXEC_PATH_LAUNCHER"
export STOCKFISH_ENV_PATH="\$STOCKFISH_EXEC_PATH_LAUNCHER"

echo "Launching Chess App from \$APP_PATH_LAUNCHER/chess_app/main.py..."
if [ -f "\$APP_PATH_LAUNCHER/chess_app/main.py" ]; then
    python "\$APP_PATH_LAUNCHER/chess_app/main.py"
else
    echo "Error: Main application script not found at \$APP_PATH_LAUNCHER/chess_app/main.py."
    echo "Please check the repository structure or run the setup script again."
    exit 1
fi

# Deactivation is tricky with GUI apps.
# If the python app exits cleanly, this might run.
# If user closes GUI window, the script waiting on 'python' might exit immediately.
# echo "Chess app exited. Deactivating virtual environment (if still active in this script's context)..."
# if type deactivate > /dev/null 2>&1; then
#    deactivate
# fi
EOL

chmod +x "$LAUNCHER_SCRIPT_PATH"
echo "Launcher script created at $LAUNCHER_SCRIPT_PATH"
echo ""

# --- Final Instructions ---
echo "--- Setup Script Finished ---"
echo "IMPORTANT: You MUST replace '<YOUR_CHESS_APP_REPO_URL_HERE>' in this script"
echo "           (setup_chess_ubuntu.sh) with the actual Git repository URL for the chess application."
echo "           Currently set to: $APP_REPO_URL"
echo ""
echo "To make this setup script executable (if you haven't already):"
echo "  chmod +x setup_chess_ubuntu.sh"
echo ""
echo "To run the application after successful setup:"
echo "  cd \"$TARGET_DIR\" && ./run_chess.sh"
echo ""
echo "To update the application and Stockfish in the future, simply re-run this setup script:"
echo "  ./setup_chess_ubuntu.sh  (if you are in $TARGET_DIR)"
echo "  OR"
echo "  /path/to/setup_chess_ubuntu.sh (if run from elsewhere)"
echo ""
echo "If Stockfish download or extraction fails, check the URL or the archive structure."
echo "The downloaded archive 'stockfish_archive.tar.gz' will be in '$STOCKFISH_DIR' for inspection in case of tar errors."
echo "--- End of Script ---"
