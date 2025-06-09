#!/bin/bash
set -e

TARGET_DIR="$HOME/chess_app"
APP_REPO_URL="<YOUR_CHESS_APP_REPO_URL_HERE>"
APP_DIR_NAME="chess-app"
STOCKFISH_URL="https://stockfishchess.org/files/stockfish-16-macOS.zip"
STOCKFISH_INTERNAL_EXEC_NAME="stockfish_binary"

echo "--- Chess App Setup Script for macOS ---"
mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

# Install dependencies via Homebrew if available
if command -v brew >/dev/null 2>&1; then
    brew install git python3 wget unzip >/dev/null
fi

if [ -d "$APP_DIR_NAME" ]; then
    cd "$APP_DIR_NAME" && git pull && cd ..
else
    git clone "$APP_REPO_URL" "$APP_DIR_NAME"
fi

cd "$APP_DIR_NAME"
python3 -m venv venv
venv/bin/pip install PySide6
cd ..

mkdir -p stockfish_engine
cd stockfish_engine
wget -O sf.zip "$STOCKFISH_URL"
unzip -o sf.zip
FOUND_EXEC=$(find . -name "stockfish*" -perm +111 -type f | head -n 1)
if [ -n "$FOUND_EXEC" ]; then
    mv "$FOUND_EXEC" "$STOCKFISH_INTERNAL_EXEC_NAME"
    chmod +x "$STOCKFISH_INTERNAL_EXEC_NAME"
fi
cd ..

cat > run_chess.sh <<EOL
#!/bin/bash
cd "$(dirname "$0")"
source "$APP_DIR_NAME/venv/bin/activate"
export STOCKFISH_ENV_PATH="$(pwd)/stockfish_engine/$STOCKFISH_INTERNAL_EXEC_NAME"
python "$APP_DIR_NAME/chess_app/main.py"
EOL
chmod +x run_chess.sh

echo "Setup finished. Run ./run_chess.sh to start the application."

