#!/bin/bash
set -e

echo "--- Chess App Setup Script for macOS ---"

# --- Configuration ---
TARGET_DIR="$HOME/chess_app_env" # Renamed to avoid conflict if app is also named chess_app
APP_SOURCE_DIR="$(pwd)" # Assumes script is run from the root of the chess app repo
# APP_NAME_FROM_SOURCE_DIR="\$(basename "\$APP_SOURCE_DIR")" # Not used, but kept for reference
STOCKFISH_DOWNLOAD_URL="https://stockfishchess.org/files/stockfish-macos-x86-64-modern.zip" # Direct link
STOCKFISH_DIR_NAME="stockfish_engine"
STOCKFISH_INTERNAL_EXEC_NAME="stockfish_binary" # Standardized name for the exec within our env
VENV_DIR_NAME="venv" # Name of the virtual environment directory
GEMMA_DIR_NAME="gemma3n"
GEMMA_MODEL_URL="https://storage.googleapis.com/gemma-models/gemma-3n.tflite"
GEMMA_VOCAB_URL="https://storage.googleapis.com/gemma-models/gemma-3n.vocab"

echo "Application Source Directory: $APP_SOURCE_DIR"
echo "Environment Target Directory for Stockfish: $TARGET_DIR"
echo "Python Virtual Environment will be in: $APP_SOURCE_DIR/$VENV_DIR_NAME"
echo "Stockfish Download URL: $STOCKFISH_DOWNLOAD_URL"
echo ""

# --- Prerequisites ---
echo "--- Checking Prerequisites ---"
if ! command -v git >/dev/null 2>&1; then
    echo "Error: git is not installed. Please install git."
    exit 1
fi
echo "git found."

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is not installed. Please install python3."
    exit 1
fi
echo "python3 found."

if ! command -v brew >/dev/null 2>&1; then
    echo "Warning: Homebrew (brew) is not installed. Attempting to continue without it for wget/unzip."
    echo "If wget or unzip are missing, you may need to install them manually or install Homebrew first."
else
    echo "Homebrew found."
fi

if ! command -v wget >/dev/null 2>&1; then
    echo "wget not found. Attempting to install wget using Homebrew..."
    if ! command -v brew >/dev/null 2>&1; then
        echo "Error: Homebrew is not installed, and wget is missing. Please install Homebrew or install wget manually."
        exit 1
    fi
    brew install wget # Show output
    if ! command -v wget >/dev/null 2>&1; then
        echo "Error: Failed to install wget using Homebrew. Please install wget manually."
        exit 1
    fi
    echo "wget installed successfully via Homebrew."
else
    echo "wget found."
fi

if ! command -v unzip >/dev/null 2>&1; then
    echo "unzip not found. Attempting to install unzip using Homebrew..."
    if ! command -v brew >/dev/null 2>&1; then
        echo "Error: Homebrew is not installed, and unzip is missing. Please install Homebrew or install unzip manually."
        exit 1
    fi
    brew install unzip # Show output
    if ! command -v unzip >/dev/null 2>&1; then
        echo "Error: Failed to install unzip using Homebrew. Please install unzip manually."
        exit 1
    fi
    echo "unzip installed successfully via Homebrew."
else
    echo "unzip found."
fi
echo "Prerequisites checked."
echo ""

# --- Target Directory for Stockfish & Python Virtual Environment ---
echo "--- Setting up Target Directory for Stockfish and Python Virtual Environment ---"
mkdir -p "$TARGET_DIR"
echo "Created/ensured target directory for Stockfish: $TARGET_DIR"

cd "$APP_SOURCE_DIR" # Navigate to app source to create venv there
echo "Creating Python virtual environment in $APP_SOURCE_DIR/$VENV_DIR_NAME..."
python3 -m venv "$VENV_DIR_NAME"
echo "Activating virtual environment and installing PySide6..."
# Use subshell to activate, install, and then it deactivates automatically
(
    source "$APP_SOURCE_DIR/$VENV_DIR_NAME/bin/activate"
    pip install PySide6
)
echo "Python dependencies (PySide6) installed in the virtual environment."
echo ""

# --- Optional Gemma 3n Setup ---
read -r -p "Download and install Gemma 3n model (~large download)? (y/N): " INSTALL_GEMMA
if [[ "$INSTALL_GEMMA" =~ ^[Yy]$ ]]; then
    echo "--- Setting up Gemma 3n ---"
    GEMMA_PATH="$TARGET_DIR/$GEMMA_DIR_NAME"
    mkdir -p "$GEMMA_PATH"
    cd "$GEMMA_PATH"
    echo "Downloading Gemma model..."
    wget -O gemma-3n.tflite "$GEMMA_MODEL_URL" && \
    wget -O gemma-3n.vocab "$GEMMA_VOCAB_URL" && echo "Gemma downloaded." || echo "Gemma download failed."
    cd "$APP_SOURCE_DIR"
fi

# --- Stockfish Setup ---
echo "--- Setting up Stockfish Chess Engine ---"
STOCKFISH_FULL_PATH="$TARGET_DIR/$STOCKFISH_DIR_NAME"
mkdir -p "$STOCKFISH_FULL_PATH"
cd "$STOCKFISH_FULL_PATH"

echo "Downloading Stockfish from $STOCKFISH_DOWNLOAD_URL..."
wget -O stockfish_archive.zip "$STOCKFISH_DOWNLOAD_URL"
echo "Stockfish archive downloaded."

echo "Extracting Stockfish..."
unzip -o stockfish_archive.zip # -o to overwrite without prompting

# Find the executable. The zip from stockfishchess.org often has a structure like:
# stockfish/stockfish-macos-x86-64-modern
# or directly the binary if it's an older version or different packaging.
FOUND_EXEC=""
# Common names or paths for Stockfish executables post-extraction
# The new link provides "stockfish-macos-x86-64-modern" inside a "stockfish" folder.
CANDIDATE_PATHS=(
    "stockfish/stockfish-macos-x86-64-modern" # Current typical path for modern builds
    "stockfish-macos-x86-64-modern"           # If extracted directly
    "stockfish"                               # Generic name
    "stockfish-x86-64-avx2"                   # Other common names
    "stockfish-x86-64"
)
for candidate in "${CANDIDATE_PATHS[@]}"; do
    if [ -f "$candidate" ] && [ -x "$candidate" ]; then
        FOUND_EXEC="$candidate"
        break
    fi
done

if [ -n "$FOUND_EXEC" ]; then
    echo "Found Stockfish executable: $FOUND_EXEC"
    # Ensure the final destination is clear if it exists from a previous run
    rm -f "./$STOCKFISH_INTERNAL_EXEC_NAME"
    mv "$FOUND_EXEC" "./$STOCKFISH_INTERNAL_EXEC_NAME"
    chmod +x "./$STOCKFISH_INTERNAL_EXEC_NAME"
    echo "Stockfish setup complete. Executable standardized to: $STOCKFISH_FULL_PATH/$STOCKFISH_INTERNAL_EXEC_NAME"
else
    echo "Error: Could not find the Stockfish executable after extraction."
    echo "Please check the archive structure from $STOCKFISH_DOWNLOAD_URL or the extraction process."
    echo "The downloaded archive 'stockfish_archive.zip' is still in $STOCKFISH_FULL_PATH for inspection."
    echo "Contents of $STOCKFISH_FULL_PATH (extraction directory):"
    ls -R . # List contents for debugging
    exit 1
fi
cd "$APP_SOURCE_DIR" # Return to app source directory
echo ""

# --- Create Launcher Script (run_chess.sh in APP_SOURCE_DIR) ---
echo "--- Creating Launcher Script (run_chess.sh) ---"
LAUNCHER_SCRIPT_PATH="$APP_SOURCE_DIR/run_chess.sh"

# Variables that need to be expanded when run_chess.sh is CREATED
# VENV_DIR_NAME, STOCKFISH_DIR_NAME, STOCKFISH_INTERNAL_EXEC_NAME are already defined in this script.
# TARGET_DIR is also defined in this script.

cat > "$LAUNCHER_SCRIPT_PATH" << EOL
#!/bin/bash
# Launcher for the Chess App
set -e

# APP_SOURCE_DIR should be the directory where this run_chess.sh script itself is located
APP_SOURCE_DIR="\$(cd "\$(dirname "\$0")" && pwd)"

# These must match the definitions in the setup_chess_macos.sh script
TARGET_DIR_ENV="$TARGET_DIR"
STOCKFISH_DIR_NAME_LAUNCHER="$STOCKFISH_DIR_NAME"
STOCKFISH_EXEC_NAME_LAUNCHER="$STOCKFISH_INTERNAL_EXEC_NAME"
VENV_DIR_LAUNCHER="$VENV_DIR_NAME"

STOCKFISH_EXEC_PATH="\$TARGET_DIR_ENV/\$STOCKFISH_DIR_NAME_LAUNCHER/\$STOCKFISH_EXEC_NAME_LAUNCHER"
VENV_ACTIVATE_PATH="\$APP_SOURCE_DIR/\$VENV_DIR_LAUNCHER/bin/activate"

echo "Chess App Launcher"
echo "Application Source: \$APP_SOURCE_DIR"
echo "Stockfish Path (from setup): \$STOCKFISH_EXEC_PATH"
echo "Venv Activation Path: \$VENV_ACTIVATE_PATH"

if [ ! -f "\$VENV_ACTIVATE_PATH" ]; then
    echo "Error: Virtual environment not found at \$VENV_ACTIVATE_PATH."
    echo "Please run the setup script (setup_chess_macos.sh) from the application root directory again."
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

GEMMA_PATH="\$TARGET_DIR_ENV/$GEMMA_DIR_NAME"
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

# Deactivation of venv is usually not needed here for GUI apps, as script exits.
# If this script were to continue, 'deactivate' would be appropriate.
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
echo "If Stockfish needs updating, you might need to manually clear $TARGET_DIR/$STOCKFISH_DIR_NAME and re-run parts of this script or download manually."
echo "--- End of Script ---"
