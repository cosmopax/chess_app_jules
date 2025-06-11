#!/bin/bash
set -e

echo "--- Chess App Setup Script for Ubuntu ---"

# --- Configuration ---
TARGET_DIR_ENV="$HOME/chess_app_env" # For Stockfish
APP_SOURCE_DIR="$(pwd)" # Assumes script is run from the root of the chess app repo
# APP_NAME_FROM_SOURCE_DIR="\$(basename "\$APP_SOURCE_DIR")" # Not used, but kept for reference
STOCKFISH_DIR_NAME="stockfish_engine"
STOCKFISH_INTERNAL_EXEC_NAME="stockfish_binary" # Standardized name for the exec within our env
STOCKFISH_DOWNLOAD_URL="https://stockfishchess.org/files/stockfish-16.1-linux-x86-64.tar.gz"
VENV_DIR_NAME="venv" # Name of the virtual environment directory
GEMMA_DIR_NAME="gemma3n"
GEMMA_MODEL_URL="https://storage.googleapis.com/gemma-models/gemma-3n.tflite"
GEMMA_VOCAB_URL="https://storage.googleapis.com/gemma-models/gemma-3n.vocab"

echo "Application Source Directory: $APP_SOURCE_DIR"
echo "Environment Target Directory (for Stockfish): $TARGET_DIR_ENV"
echo "Python Virtual Environment will be in: $APP_SOURCE_DIR/$VENV_DIR_NAME"
echo "Stockfish Download URL: $STOCKFISH_DOWNLOAD_URL"
echo ""

# --- System Dependencies ---
echo "--- Checking and Installing System Dependencies ---"
# Ensure non-interactive frontend for apt commands if script is fully automated
export DEBIAN_FRONTEND=noninteractive
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip wget tar
echo "System dependencies checked/installed."
echo ""

# --- Target Directory for Stockfish & Python Virtual Environment ---
echo "--- Setting up Python Virtual Environment ---"
cd "$APP_SOURCE_DIR" # Navigate to app source to create venv there
echo "Creating Python virtual environment in $APP_SOURCE_DIR/$VENV_DIR_NAME..."
python3 -m venv "$VENV_DIR_NAME"
echo "Activating virtual environment and installing PySide6..."
# Use subshell to activate, install, and then it deactivates automatically
(
    source "$APP_SOURCE_DIR/$VENV_DIR_NAME/bin/activate"
    pip install PySide6
)
echo "Python dependencies (PySide6) installed in $APP_SOURCE_DIR/$VENV_DIR_NAME."
echo ""

# --- Optional Gemma 3n Setup ---
read -r -p "Download and install Gemma 3n model (~large download)? (y/N): " INSTALL_GEMMA
if [[ "$INSTALL_GEMMA" =~ ^[Yy]$ ]]; then
    echo "--- Setting up Gemma 3n ---"
    GEMMA_PATH="$TARGET_DIR_ENV/$GEMMA_DIR_NAME"
    mkdir -p "$GEMMA_PATH"
    cd "$GEMMA_PATH"
    echo "Downloading Gemma model..."
    wget -O gemma-3n.tflite "$GEMMA_MODEL_URL" && \
    wget -O gemma-3n.vocab "$GEMMA_VOCAB_URL" && echo "Gemma downloaded." || echo "Gemma download failed."
    cd "$APP_SOURCE_DIR"
fi

# --- Stockfish Setup ---
echo "--- Setting up Stockfish Chess Engine in $TARGET_DIR_ENV ---"
STOCKFISH_FULL_PATH="$TARGET_DIR_ENV/$STOCKFISH_DIR_NAME"
mkdir -p "$STOCKFISH_FULL_PATH"
cd "$STOCKFISH_FULL_PATH"

echo "Removing old Stockfish version if any..."
rm -rf ./* # Clear out the directory before downloading new version

echo "Downloading Stockfish from $STOCKFISH_DOWNLOAD_URL..."
if wget -O stockfish_archive.tar.gz "$STOCKFISH_DOWNLOAD_URL"; then
    echo "Stockfish archive downloaded."
    echo "Extracting Stockfish..."
    # Attempt to extract. The provided URL for 16.1 tar.gz contains a top-level dir like 'stockfish-16.1-linux-x86-64'
    # We want to strip that directory to get its contents directly.
    # Using --strip-components=1 assumes the tarball has a single top-level directory.
    if tar -xvzf stockfish_archive.tar.gz --strip-components=1; then
        echo "Stockfish extracted."

        FOUND_EXEC=""
        # Common names for Stockfish executables post-extraction from this specific tarball
        # The 'stockfish-16.1-linux-x86-64' tarball contains executables like:
        # stockfish-x86-64-avx2, stockfish-x86-64-bmi2, stockfish-x86-64-modern, stockfish-x86-64-popcnt
        # We should pick one, e.g., 'stockfish-x86-64-modern' or a generic 'stockfish' if it exists.
        # The tar structure might be stockfish/stockfish-.... so check that too.
        COMMON_NAMES=(
            "stockfish"                             # If a generic one is present
            "stockfish-x86-64-modern"             # A good default modern version
            "stockfish-x86-64-avx2"               # Common optimized version
            "stockfish-x86-64-bmi2"
            "stockfish-16.1-linux-x86-64"         # Sometimes the main binary has version in name
        )
        for name in "${COMMON_NAMES[@]}"; do
            if [ -f "$name" ] && [ -x "$name" ]; then
                FOUND_EXEC="$name"
                break
            fi
        done

        if [ -n "$FOUND_EXEC" ]; then
            echo "Found Stockfish executable: $FOUND_EXEC"
            rm -f "./$STOCKFISH_INTERNAL_EXEC_NAME" # Remove if already exists
            mv "$FOUND_EXEC" "./$STOCKFISH_INTERNAL_EXEC_NAME"
            chmod +x "./$STOCKFISH_INTERNAL_EXEC_NAME"
            echo "Stockfish setup complete. Executable standardized to: $STOCKFISH_FULL_PATH/$STOCKFISH_INTERNAL_EXEC_NAME"
        else
            echo "Error: Could not find a suitable Stockfish executable after extraction."
            echo "Please check the archive structure at $STOCKFISH_DOWNLOAD_URL or the extraction process."
            echo "The downloaded archive stockfish_archive.tar.gz is still in $STOCKFISH_FULL_PATH for inspection."
            echo "Contents of $STOCKFISH_FULL_PATH (extraction directory):"
            ls -R . # List contents for debugging
            exit 1
        fi
    else
        echo "Error: Failed to extract Stockfish archive. The archive might be corrupted or the structure unexpected."
        echo "The downloaded archive stockfish_archive.tar.gz is still in $STOCKFISH_FULL_PATH for inspection."
        exit 1
    fi
else
    echo "Error: wget failed to download Stockfish from $STOCKFISH_DOWNLOAD_URL."
    echo "Skipping further Stockfish processing for this run."
    exit 1
fi
cd "$APP_SOURCE_DIR" # Return to app source directory
echo ""

# --- Create Launcher Script (run_chess.sh in APP_SOURCE_DIR) ---
echo "--- Creating Launcher Script (run_chess.sh) ---"
LAUNCHER_SCRIPT_PATH="$APP_SOURCE_DIR/run_chess.sh"

# Variables that need to be expanded when run_chess.sh is CREATED
# VENV_DIR_NAME, STOCKFISH_DIR_NAME, STOCKFISH_INTERNAL_EXEC_NAME are already defined in this script.
# TARGET_DIR_ENV is also defined in this script.

cat > "$LAUNCHER_SCRIPT_PATH" << EOL
#!/bin/bash
# Launcher for the Chess App
set -e

# APP_SOURCE_DIR should be the directory where this run_chess.sh script itself is located
APP_SOURCE_DIR="\$(cd "\$(dirname "\$0")" && pwd)"

# These must match the definitions in the setup_chess_ubuntu.sh script
TARGET_DIR_ENV_LAUNCHER="$TARGET_DIR_ENV"
STOCKFISH_DIR_NAME_LAUNCHER="$STOCKFISH_DIR_NAME"
STOCKFISH_EXEC_NAME_LAUNCHER="$STOCKFISH_INTERNAL_EXEC_NAME"
VENV_DIR_LAUNCHER="$VENV_DIR_NAME"

STOCKFISH_EXEC_PATH="\$TARGET_DIR_ENV_LAUNCHER/\$STOCKFISH_DIR_NAME_LAUNCHER/\$STOCKFISH_EXEC_NAME_LAUNCHER"
VENV_ACTIVATE_PATH="\$APP_SOURCE_DIR/\$VENV_DIR_LAUNCHER/bin/activate"

echo "Chess App Launcher"
echo "Application Source: \$APP_SOURCE_DIR"
echo "Environment Base (Stockfish): \$TARGET_DIR_ENV_LAUNCHER"
echo "Stockfish Path: \$STOCKFISH_EXEC_PATH"
echo "Venv Path: \$VENV_ACTIVATE_PATH"

if [ ! -f "\$VENV_ACTIVATE_PATH" ]; then
    echo "Error: Virtual environment not found at \$VENV_ACTIVATE_PATH."
    echo "Please run the setup script (setup_chess_ubuntu.sh) from the application root directory again."
    exit 1
fi
source "\$VENV_ACTIVATE_PATH"
echo "Python virtual environment activated."

if [ ! -x "\$STOCKFISH_EXEC_PATH" ]; then
    echo "Error: Stockfish executable not found or not executable at \$STOCKFISH_EXEC_PATH."
    echo "Please ensure Stockfish was downloaded and set up correctly by the setup script."
    exit 1
fi
# Export for the application to use
export STOCKFISH_ENV_PATH="\$STOCKFISH_EXEC_PATH"
echo "STOCKFISH_ENV_PATH set to: \$STOCKFISH_ENV_PATH"

GEMMA_PATH="\$TARGET_DIR_ENV_LAUNCHER/$GEMMA_DIR_NAME"
if [ -f "\$GEMMA_PATH/gemma-3n.tflite" ]; then
    export GEMMA3N_MODEL_PATH="\$GEMMA_PATH/gemma-3n.tflite"
    export GEMMA3N_VOCAB_PATH="\$GEMMA_PATH/gemma-3n.vocab"
    echo "Gemma 3n configured at \$GEMMA_PATH"
fi

APP_MAIN_SCRIPT="\$APP_SOURCE_DIR/chess_app/main.py"
if [ ! -f "\$APP_MAIN_SCRIPT" ]; then
    echo "Error: Main application script not found at \$APP_MAIN_SCRIPT."
    echo "Please ensure the application structure is correct and you are running this from the app root."
    exit 1
fi
echo "Launching Chess App: python \$APP_MAIN_SCRIPT"
python "\$APP_MAIN_SCRIPT"

echo "Chess App exited."
EOL

chmod +x "$LAUNCHER_SCRIPT_PATH"
echo "Launcher script created at $LAUNCHER_SCRIPT_PATH"
echo ""

# --- Final Instructions ---
echo "--- Setup Script Finished ---"
echo "This script assumes it is run from the root directory of your chess application's source code."
echo ""
echo "To run the application after successful setup:"
echo "  cd $APP_SOURCE_DIR"
echo "  ./run_chess.sh"
echo ""
echo "To update Python dependencies in the future (from $APP_SOURCE_DIR):"
echo "  source $VENV_DIR_NAME/bin/activate"
echo "  pip install --upgrade PySide6 some_other_package"
echo "  deactivate"
echo ""
echo "If Stockfish needs updating, you might need to manually clear $TARGET_DIR_ENV/$STOCKFISH_DIR_NAME and re-run parts of this script or download manually."
echo "--- End of Script ---"
