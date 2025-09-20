#!/bin/bash
# Setup script for development environment
# Installs system packages if possible, creates a venv and installs dev dependencies
set -e

VENV_DIR="dev_venv"

# Detect operating system
OS=""
UNAME=$(uname)
if [[ "$UNAME" == "Darwin" ]]; then
    OS="macOS"
elif [[ "$UNAME" == "Linux" ]]; then
    if command -v apt-get >/dev/null 2>&1; then
        OS="Ubuntu"
    else
        OS="Linux"
    fi
else
    OS="Unknown"
fi

echo "Detected OS: $OS"

# Install system packages
if [[ "$OS" == "Ubuntu" ]]; then
    echo "Installing required system packages with apt..."
    sudo apt-get update
    sudo apt-get install -y python3 python3-venv python3-pip git
elif [[ "$OS" == "macOS" ]]; then
    if ! command -v brew >/dev/null 2>&1; then
        echo "Homebrew is required but not installed. Please install Homebrew first: https://brew.sh"
        exit 1
    fi
    echo "Installing Python3 and git with Homebrew..."
    brew update
    brew install python git || true
fi

# Create and activate venv
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# Install Python dev requirements
pip install -r dev-requirements.txt

# Verify common tools are available
MISSING=()
for TOOL in flake8 black pytest; do
    if ! command -v "$TOOL" >/dev/null 2>&1; then
        MISSING+=("$TOOL")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "Warning: missing tools after installation: ${MISSING[*]}"
    echo "Ensure your network connection allows pip to download packages or install them manually."
fi

echo "Development environment ready. Activate with 'source $VENV_DIR/bin/activate'"
