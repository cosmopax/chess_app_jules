#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "--- Universal Chess App Installer ---"
echo "This script downloads and sets up the Chess Application"
echo "including the newest Stockfish engine."
echo ""

# Optional non-interactive mode. Use -y or --yes to skip prompts
NON_INTERACTIVE=0
for arg in "$@"; do
    case "$arg" in
        -y|--yes)
            NON_INTERACTIVE=1
            shift
            ;;
    esac
done

# --- Configuration ---
# If the current user is 'cosmopax' keep a hard coded default path
# otherwise default to a directory under the user's HOME.
if [ "$(whoami)" = "cosmopax" ]; then
    DEFAULT_INSTALL_DIR="/home/cosmopax/MyChessApp"
else
    DEFAULT_INSTALL_DIR="$HOME/MyChessApp"
fi
# IMPORTANT: Replace with the actual default URL of your chess application repository
DEFAULT_REPO_URL="https://github.com/cosmopax/chess_app_jules.git"

# --- OS Detection ---
OS_TYPE=""
OS_NAME=$(uname) # Store for clarity

if [[ "$OS_NAME" == "Darwin" ]]; then
    OS_TYPE="macOS"
elif [[ "$OS_NAME" == "Linux" ]]; then
    # Further check for Debian/Ubuntu based systems for apt
    if command -v apt-get >/dev/null 2>&1; then
        OS_TYPE="Ubuntu" # Generic term for Debian-based for this script's purpose
    else
        echo "Error: Unsupported Linux distribution. This script currently supports Debian-based systems (like Ubuntu) that use 'apt'."
        exit 1
    fi
else
    echo "Error: Unsupported operating system '$OS_NAME'. This script supports macOS and Debian-based Linux (like Ubuntu)."
    exit 1
fi
echo "Detected Operating System: $OS_TYPE"
echo ""

# --- User Input ---
if [ "$NON_INTERACTIVE" -eq 1 ]; then
    REPO_URL="$DEFAULT_REPO_URL"
else
    read -r -p "Enter the Git repository URL for the Chess App (default: $DEFAULT_REPO_URL): " REPO_URL
    REPO_URL=${REPO_URL:-$DEFAULT_REPO_URL}
fi

if [ "$NON_INTERACTIVE" -eq 1 ]; then
    INSTALL_DIR="$DEFAULT_INSTALL_DIR"
else
    read -r -p "Enter the directory where you want to install the Chess App (default: $DEFAULT_INSTALL_DIR): " INSTALL_DIR
    INSTALL_DIR=${INSTALL_DIR:-$DEFAULT_INSTALL_DIR}
fi

# Expand INSTALL_DIR path (e.g., if ~ is used by user)
INSTALL_DIR_EXPANDED=$(eval echo "$INSTALL_DIR")

echo ""
echo "--- Configuration Summary ---"
echo "Repository URL: $REPO_URL"
echo "Installation Directory: $INSTALL_DIR_EXPANDED"
echo ""

if [ "$NON_INTERACTIVE" -eq 1 ]; then
    CONFIRM="y"
else
    read -r -p "Proceed with installation? (y/n): " CONFIRM
    if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
        echo "Installation cancelled by user."
        exit 0
    fi
fi
echo ""

# --- Prerequisites ---
echo "--- Checking Prerequisites ---"
if ! command -v git >/dev/null 2>&1; then
    echo "Error: git is not installed. Please install git first."
    echo "On macOS (using Homebrew): brew install git"
    echo "On Ubuntu/Debian: sudo apt update && sudo apt install -y git"
    exit 1
fi
echo "Git is installed."
echo ""

# --- Installation ---
echo "--- Starting Installation ---"
if [ -d "$INSTALL_DIR_EXPANDED" ]; then
    echo "Warning: Installation directory '$INSTALL_DIR_EXPANDED' already exists."
    if [ "$NON_INTERACTIVE" -eq 1 ]; then
        echo "Non-interactive mode: removing existing directory."
        rm -rf "$INSTALL_DIR_EXPANDED"
    else
        read -r -p "Do you want to remove it and continue? (y/n) THIS IS DESTRUCTIVE: " OVERWRITE_CONFIRM
        if [[ "$OVERWRITE_CONFIRM" =~ ^[Yy]$ ]]; then
            echo "Removing existing directory: $INSTALL_DIR_EXPANDED"
            rm -rf "$INSTALL_DIR_EXPANDED"
        else
            echo "Installation aborted. Please choose a different directory or manually remove the existing one."
            exit 1
        fi
    fi
fi

echo "Creating installation directory: $INSTALL_DIR_EXPANDED"
mkdir -p "$INSTALL_DIR_EXPANDED"

echo "Cloning repository '$REPO_URL' into '$INSTALL_DIR_EXPANDED'..."
if git clone "$REPO_URL" "$INSTALL_DIR_EXPANDED"; then
    echo "Repository cloned successfully."
else
    echo "Error: Failed to clone repository. Please check the URL and your internet connection."
    # Clean up created directory if clone failed
    # Note: rm -rf on a variable path should be used with caution, but here it's controlled.
    rm -rf "$INSTALL_DIR_EXPANDED"
    exit 1
fi
echo ""

# Navigate into the cloned repository
echo "Changing directory to $INSTALL_DIR_EXPANDED"
cd "$INSTALL_DIR_EXPANDED"
echo "Current directory: $(pwd)"
echo ""

# --- Run OS-specific setup script ---
SETUP_SCRIPT_NAME=""
if [[ "$OS_TYPE" == "macOS" ]]; then
    SETUP_SCRIPT_NAME="setup_chess_macos.sh"
elif [[ "$OS_TYPE" == "Ubuntu" ]]; then # Covers Debian-based
    SETUP_SCRIPT_NAME="setup_chess_ubuntu.sh"
fi

if [ -f "$SETUP_SCRIPT_NAME" ]; then
    echo "Found setup script: $SETUP_SCRIPT_NAME"
    echo "Making it executable..."
    chmod +x "$SETUP_SCRIPT_NAME"
    echo "Running setup script ($(pwd)/$SETUP_SCRIPT_NAME)..."
    # Run the script directly. It will handle its own sourcing/subshells if needed.
    if ./"$SETUP_SCRIPT_NAME"; then
        echo "Setup script completed successfully."
    else
        echo "Error: The setup script ($(pwd)/$SETUP_SCRIPT_NAME) failed."
        echo "Please check the output above for details."
        # Note: The setup script itself should have good error reporting.
        exit 1
    fi
else
    echo "Error: Setup script '$SETUP_SCRIPT_NAME' not found in the cloned repository ($INSTALL_DIR_EXPANDED)."
    echo "Please ensure the repository contains the correct setup scripts for $OS_TYPE."
    exit 1
fi
echo ""

# --- Final Instructions ---
echo "--- Installation Finished ---"
echo "The Chess Application has been installed in: $INSTALL_DIR_EXPANDED"
echo ""
echo "To run the application:"
echo "1. Navigate to the application directory:"
echo "   cd \"$INSTALL_DIR_EXPANDED\"" # Quoted for safety if path has spaces, though eval echo handled ~
echo "2. Run the launcher script:"
echo "   ./run_chess.sh"
echo ""
echo "Enjoy the Chess App!"
echo "--- End of Installer ---"
