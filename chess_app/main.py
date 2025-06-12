import logging
import os

# It's good practice to have configuration like paths managed centrally or discovered.
# For this example, we'll define a default path for Stockfish.
# In a real app, this might come from a config file, environment variable, or a discovery mechanism.
import shutil  # Ensure shutil is imported
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from chess_app.ui.main_window import MainWindow

# Attempt to locate Stockfish. Users might need to set STOCKFISH_ENV_PATH or have it in PATH.
DEFAULT_STOCKFISH_PATH = "stockfish" # Assume stockfish is in PATH
logger = logging.getLogger(__name__) # Define logger globally for find_stockfish_path

def find_stockfish_path():
    """
    Tries to find a usable Stockfish executable path.
    Returns the path string if found, otherwise None.
    """
    logger.info("Attempting to find Stockfish executable...")

    # 1. Check environment variable STOCKFISH_ENV_PATH
    env_path = os.getenv("STOCKFISH_ENV_PATH")
    if env_path:
        logger.info(f"STOCKFISH_ENV_PATH is set to: {env_path}")
        if os.path.isfile(env_path) and os.access(env_path, os.X_OK):
            logger.info(f"Found valid Stockfish executable via STOCKFISH_ENV_PATH: {env_path}")
            return env_path
        else:
            logger.error(f"STOCKFISH_ENV_PATH ('{env_path}') is set but is not a valid or executable file. This path will be ignored.")
            return None # Explicitly return None if env var is set but invalid

    # 2. If STOCKFISH_ENV_PATH is not set or was invalid (already returned None), try DEFAULT_STOCKFISH_PATH
    logger.info(f"Checking for '{DEFAULT_STOCKFISH_PATH}' in system PATH using shutil.which...")
    which_path = shutil.which(DEFAULT_STOCKFISH_PATH)

    if which_path:
        # shutil.which returns the absolute path if found and executable.
        # We still do an explicit os.access check for robustness, though shutil.which usually implies it.
        if os.access(which_path, os.X_OK):
            logger.info(f"Found executable Stockfish in PATH: {which_path} (using command '{DEFAULT_STOCKFISH_PATH}')")
            # Return the command string, as engine Popen usually handles PATH resolution well.
            # Or return which_path if absolute path is preferred for Popen. For now, stick to command.
            return DEFAULT_STOCKFISH_PATH
        else:
            # This case should be rare if shutil.which returned a path.
            logger.error(f"shutil.which found '{DEFAULT_STOCKFISH_PATH}' at '{which_path}', but it's not executable. This should not happen.")
            return None
    else:
        logger.error(f"Default Stockfish command '{DEFAULT_STOCKFISH_PATH}' not found in system PATH.")
        return None

    # Fallback should not be reached if logic is correct, means something was missed.
    # However, to be safe and satisfy original intent of returning something if all fails:
    # logger.warning("Stockfish path detection failed unexpectedly. Returning None.")
    # return None # All explicit checks failed

def main():
    # Configure logging as the first step
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Application starting...") # Now logger is configured

    app = QApplication(sys.argv)

    STOCKFISH_PATH = find_stockfish_path()

    if STOCKFISH_PATH is None:
        logger.critical("Stockfish engine could not be found or configured correctly.")
        QMessageBox.critical(
            None, # Parent widget
            "Stockfish Not Found",
            "Stockfish engine not found or configured correctly.\n"
            "Please ensure Stockfish is installed and in your system PATH, "
            "or set the STOCKFISH_ENV_PATH environment variable to the full executable path.\n\n"
            "The application will now exit."
        )
        sys.exit(1)

    logger.info(f"Stockfish path configured to: {STOCKFISH_PATH}")

    try:
        main_window = MainWindow(engine_path=STOCKFISH_PATH)
        main_window.show()
    except Exception as e:
        logger.critical(f"Failed to create or show MainWindow: {e}", exc_info=True)
        QMessageBox.critical(
            None,
            "Application Error",
            f"A critical error occurred while starting the application: {e}"
        )
        sys.exit(1)

    sys.exit(app.exec())

if __name__ == '__main__':
    main()

