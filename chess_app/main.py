import sys
import os
import logging
from PySide6.QtWidgets import QApplication, QMessageBox

from chess_app.ui.main_window import MainWindow
# It's good practice to have configuration like paths managed centrally or discovered.
# For this example, we'll define a default path for Stockfish.
# In a real app, this might come from a config file, environment variable, or a discovery mechanism.

# Attempt to locate Stockfish. Users might need to set STOCKFISH_ENV_PATH or have it in PATH.
DEFAULT_STOCKFISH_PATH = "stockfish" # Assume stockfish is in PATH

def find_stockfish_path():
    """Tries to find a usable Stockfish executable path."""
    # 1. Check environment variable
    env_path = os.getenv("STOCKFISH_ENV_PATH")
    if env_path and os.path.isfile(env_path) and os.access(env_path, os.X_OK):
        logger.info(f"Using Stockfish from STOCKFISH_ENV_PATH: {env_path}")
        return env_path

    # 2. Check common known paths (example, adjust as needed or use a proper discovery)
    #    This is highly OS-dependent and often not robust.
    # common_paths = ["/usr/games/stockfish", "/usr/local/bin/stockfish", "./stockfish"]
    # for path_to_check in common_paths:
    #     if os.path.isfile(path_to_check) and os.access(path_to_check, os.X_OK):
    #         logger.info(f"Found Stockfish at common path: {path_to_check}")
    #         return path_to_check

    # 3. Rely on it being in system PATH (DEFAULT_STOCKFISH_PATH = "stockfish")
    #    The EngineWorker will try to call this. We can't easily check os.access on
    #    something that needs PATH resolution without `shutil.which` (Python 3.3+).
    #    For simplicity, we'll just return the default and let EngineWorker try it.
    #    A more robust check here would involve `shutil.which("stockfish")`.

    # If using Python 3.3+, shutil.which is the best way to check PATH
    try:
        import shutil
        which_path = shutil.which(DEFAULT_STOCKFISH_PATH)
        if which_path and os.access(which_path, os.X_OK):
            logger.info(f"Found Stockfish in PATH: {which_path} (using '{DEFAULT_STOCKFISH_PATH}')")
            return DEFAULT_STOCKFISH_PATH # Return the command, not the full path, as Popen handles PATH
    except ImportError:
        logger.warning("shutil.which not available (requires Python 3.3+). Will try default stockfish command.")

    logger.info(f"Assuming '{DEFAULT_STOCKFISH_PATH}' is in system PATH or configured elsewhere.")
    return DEFAULT_STOCKFISH_PATH


# Configure logging for the main application
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# This STOCKFISH_PATH will be passed to EngineWorker via MainWindow
# The EngineWorker itself will then try to use this path/command.
STOCKFISH_PATH = find_stockfish_path()


def main():
    logger.info("Application starting...")
    app = QApplication(sys.argv)

    # Pre-flight check for Stockfish (basic check, EngineWorker does the realpopen)
    # This is a simplified check. A more robust check would try to run `stockfish uci` briefly.
    # The EngineWorker's initialization is the more definitive check.

    # We use the path/command determined by find_stockfish_path() to initialize MainWindow,
    # which in turn passes it to EngineWorker.
    # A critical QMessageBox here might be too early if STOCKFISH_PATH is just "stockfish" (for PATH lookup).
    # The EngineWorker's own error handling (which MainWindow reacts to) is probably better.
    # However, if an explicit path was given via ENV and it's invalid, a warning is good.

    env_path_check = os.getenv("STOCKFISH_ENV_PATH")
    if env_path_check and not (os.path.isfile(env_path_check) and os.access(env_path_check, os.X_OK)):
         QMessageBox.warning(
            None, # Parent widget
            "Stockfish Configuration Warning",
            f"The Stockfish path specified in STOCKFISH_ENV_PATH ({env_path_check}) is not valid or not executable.\n"
            f"The application will attempt to use '{DEFAULT_STOCKFISH_PATH}' from the system PATH."
        )
    elif STOCKFISH_PATH != DEFAULT_STOCKFISH_PATH and not (os.path.isfile(STOCKFISH_PATH) and os.access(STOCKFISH_PATH, os.X_OK)):
        # This case covers if find_stockfish_path returned a specific local path that's invalid.
        # It's less likely with the current find_stockfish_path logic which prefers returning the command.
        QMessageBox.critical(
            None,
            "Stockfish Not Found",
            f"Stockfish executable not found or not executable at the determined path: {STOCKFISH_PATH}.\n"
            "Please ensure Stockfish is installed and in your PATH, or set the STOCKFISH_ENV_PATH environment variable."
        )
        # sys.exit(1) # Exiting here might be too abrupt. Let MainWindow try to initialize.

    try:
        main_window = MainWindow(engine_path=STOCKFISH_PATH)
        main_window.show()
    except Exception as e:
        logger.critical(f"Failed to create or show MainWindow: {e}", exc_info=True)
        QMessageBox.critical(
            None,
            "Application Error",
            f"An critical error occurred while starting the application: {e}"
        )
        sys.exit(1)

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
```
