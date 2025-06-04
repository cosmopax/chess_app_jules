import sys
import logging
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
                               QPushButton, QTextEdit, QLabel, QAction, QMessageBox)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QObject
import chess
import chess.svg

# Assuming EngineWorker is in chess_app.engine.engine_worker
# Adjust the import path if your project structure is different.
# For this example, we might need to ensure PYTHONPATH is set up correctly
# if running this file directly and chess_app is a package.
from chess_app.engine.engine_worker import EngineWorker, EngineState

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MainWindowSignals(QObject):
    # Custom signals that can be emitted from background threads or EngineWorker callbacks
    # For simplicity, direct calls and state polling will be used more, but signals are good practice.
    analysis_update_ready = Signal(dict) # If EngineWorker were to provide analysis via callback
    best_move_ready = Signal(chess.Move) # If EngineWorker provided move via callback
    engine_state_changed_signal = Signal(EngineState)

class MainWindow(QMainWindow):
    def __init__(self, engine_path="stockfish"):
        super().__init__()
        self.setWindowTitle("Chess AI Interface")
        self.setGeometry(100, 100, 800, 600)

        self.board = chess.Board()
        self.engine_worker = None # Will be initialized later
        self.engine_path = engine_path

        # UI Flags (to be reviewed based on EngineWorker state)
        self.is_engine_thinking_ui_flag = False # UI's perception, should sync with EngineState.THINKING
        self.analysis_is_on_ui_flag = False # UI's perception, should sync with EngineState.ANALYZING

        self._init_ui()
        self._create_menu()

        try:
            logger.info(f"Initializing EngineWorker with path: {self.engine_path}")
            self.engine_worker = EngineWorker(engine_path=self.engine_path)
        except Exception as e:
            logger.critical(f"Failed to initialize EngineWorker: {e}", exc_info=True)
            QMessageBox.critical(self, "Engine Error", f"Failed to initialize chess engine: {e}")
            # Potentially disable engine-related UI elements or close app
            # For now, we'll let it run but engine features won't work.
            self.start_analysis_button.setEnabled(False)
            self.request_move_button.setEnabled(False)

        # Timer to update UI based on engine state, and potentially to poll for analysis
        self.ui_update_timer = QTimer(self)
        self.ui_update_timer.timeout.connect(self.update_ui_from_engine_state)
        self.ui_update_timer.start(500) # Update every 500ms

        self.signals = MainWindowSignals()
        # Example connections if EngineWorker had signals or callbacks that emit these:
        # self.signals.analysis_update_ready.connect(self.handle_engine_analysis)
        # self.signals.best_move_ready.connect(self.handle_engine_move_signal)
        # self.signals.engine_state_changed_signal.connect(self.on_engine_state_changed)


    def _init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Chess board display (simple text for now, could be SVG or QGraphicsView)
        self.board_display = QTextEdit()
        self.board_display.setReadOnly(True)
        self.board_display.setFontPointSize(14)
        self.layout.addWidget(self.board_display)
        self.update_board_display()

        # Analysis display
        self.analysis_display = QTextEdit()
        self.analysis_display.setReadOnly(True)
        self.analysis_display.setFixedHeight(100)
        self.layout.addWidget(self.analysis_display)

        # Status label
        self.status_label = QLabel("Status: Initializing...")
        self.layout.addWidget(self.status_label)

        # Buttons
        self.button_layout = QHBoxLayout()
        self.start_analysis_button = QPushButton("Start Analysis")
        self.start_analysis_button.clicked.connect(self.toggle_analysis_clicked)
        self.button_layout.addWidget(self.start_analysis_button)

        self.request_move_button = QPushButton("Request Engine Move")
        self.request_move_button.clicked.connect(self.request_engine_move_clicked)
        self.button_layout.addWidget(self.request_move_button)

        self.reset_board_button = QPushButton("Reset Board")
        self.reset_board_button.clicked.connect(self.reset_board)
        self.button_layout.addWidget(self.reset_board_button)

        self.layout.addLayout(self.button_layout)

    def _create_menu(self):
        self.menubar = self.menuBar()
        file_menu = self.menubar.addMenu("&File")

        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def update_board_display(self):
        # In a real app, you'd use chess.svg.board or a custom QGraphicsScene
        self.board_display.setText(str(self.board))

    def reset_board(self):
        self.board.reset()
        self.update_board_display()
        self.analysis_display.clear()
        self.status_label.setText("Status: Board Reset. Idle.")
        if self.engine_worker and self.engine_worker.get_state() == EngineState.ANALYZING:
            logger.info("Board reset while analysis was on. Stopping analysis.")
            self.engine_worker.stop_analysis() # This is blocking
        self.update_ui_from_engine_state()


    def toggle_analysis_clicked(self):
        if not self.engine_worker or not self.engine_worker.engine:
            QMessageBox.warning(self, "Engine Not Ready", "The chess engine is not available.")
            return

        current_state = self.engine_worker.get_state()
        if current_state == EngineState.ANALYZING:
            logger.info("UI: Requesting to stop analysis.")
            self.status_label.setText("Status: Stopping analysis...")
            stopped_cleanly = self.engine_worker.stop_analysis() # This is a blocking call
            if not stopped_cleanly:
                QMessageBox.warning(self,
                                    "Analysis Stop Issue",
                                    "The analysis engine did not confirm stopping in time. "
                                    "Its state has been reset, but it might not have stopped cleanly.")
            # State update will be handled by update_ui_from_engine_state
        elif current_state == EngineState.IDLE:
            logger.info("UI: Requesting to start analysis.")
            self.status_label.setText("Status: Starting analysis...")
            # Make a copy of the board for the engine to use
            self.engine_worker.start_analysis(self.board.copy())
            # State update will be handled by update_ui_from_engine_state
        else:
            QMessageBox.information(self, "Engine Busy", f"Engine is currently {current_state.name}. Cannot toggle analysis now.")

        self.update_ui_from_engine_state() # Update UI immediately after action

    def request_engine_move_clicked(self):
        if not self.engine_worker or not self.engine_worker.engine:
            QMessageBox.warning(self, "Engine Not Ready", "The chess engine is not available.")
            return

        if self.board.is_game_over():
            QMessageBox.information(self, "Game Over", "The game is over. Cannot request move.")
            return

        current_state = self.engine_worker.get_state()
        if current_state == EngineState.IDLE:
            logger.info("UI: Requesting engine move.")
            self.status_label.setText("Status: Engine is thinking...")
            self.is_engine_thinking_ui_flag = True # Set flag for UI responsiveness
            self.update_ui_elements() # Disable buttons etc.

            # The new engine_worker.request_best_move is blocking and returns the move.
            # This call will block the UI thread. For a responsive UI, this should be in a QThread.
            # For this iteration, we'll accept the UI freeze during engine thinking.
            time_limit_ms = 1000 # Example: 1 second

            # Make a copy of the board for the engine
            move = self.engine_worker.request_best_move(self.board.copy(), time_limit_ms / 1000.0)

            self.is_engine_thinking_ui_flag = False # Reset flag
            if move:
                self.handle_engine_move(move)
            else:
                QMessageBox.warning(self, "No Move", "Engine did not return a move or an error occurred.")
                self.status_label.setText("Status: Idle. Engine failed to find a move.")
            self.update_ui_elements() # Re-enable buttons
            self.update_ui_from_engine_state() # Refresh state display
        else:
            QMessageBox.information(self, "Engine Busy", f"Engine is currently {current_state.name}. Cannot request move now.")


    def handle_engine_move(self, move: chess.Move):
        if move and move in self.board.legal_moves:
            logger.info(f"UI: Applying engine move: {move.uci()}")
            self.board.push(move)
            self.update_board_display()
            self.status_label.setText(f"Status: Engine played {move.uci()}. Idle.")
            if self.board.is_game_over():
                self.handle_game_over()
        elif move:
            logger.warning(f"UI: Engine returned an illegal move: {move.uci()} for board {self.board.fen()}")
            QMessageBox.warning(self, "Illegal Move", f"Engine suggested an illegal move: {move.uci()}")
            self.status_label.setText("Status: Engine suggested illegal move. Idle.")
        else:
            # This case is handled in request_engine_move_clicked if move is None
            pass
        self.update_ui_elements()

    # This method would be connected to a signal if EngineWorker streamed analysis
    def handle_engine_analysis(self, analysis_data: dict | None):
        """Display analysis information from the engine."""
        if not analysis_data:
            self.analysis_display.clear()
            return

        score = analysis_data.get("score")
        pv = analysis_data.get("pv")

        text_parts = []
        if score is not None:
            text_parts.append(f"Score: {score}")
        if pv:
            pv_str = " ".join(move.uci() for move in pv)
            text_parts.append(f"PV: {pv_str}")

        self.analysis_display.setText(" | ".join(text_parts))


    def update_ui_from_engine_state(self):
        if not self.engine_worker:
            self.status_label.setText("Status: Engine not available.")
            self.start_analysis_button.setEnabled(False)
            self.request_move_button.setEnabled(False)
            return

        state = self.engine_worker.get_state()

        # Update UI flags based on actual engine state
        self.analysis_is_on_ui_flag = (state == EngineState.ANALYZING)
        self.is_engine_thinking_ui_flag = (state == EngineState.THINKING) # Should be brief, as request_best_move blocks

        if state == EngineState.IDLE:
            self.status_label.setText("Status: Idle")
            self.analysis_display.clear() # Clear analysis when idle
        elif state == EngineState.ANALYZING:
            self.status_label.setText("Status: Analyzing...")
            info = self.engine_worker.get_latest_analysis_info()
            self.handle_engine_analysis(info)
        elif state == EngineState.THINKING:
            # This state is usually brief due to blocking call, status set in request_engine_move_clicked
            self.status_label.setText("Status: Engine is thinking...")
        elif state == EngineState.SHUTDOWN:
            self.status_label.setText("Status: Engine offline or error. Check config/restart.")
        else:
            self.status_label.setText(f"Status: Engine state {state.name}")

        self.update_ui_elements()

    def update_ui_elements(self):
        if not self.engine_worker or not self.engine_worker.engine:
            self.start_analysis_button.setText("Start Analysis")
            self.start_analysis_button.setEnabled(False)
            self.request_move_button.setEnabled(False)
            return

        state = self.engine_worker.get_state()

        if state == EngineState.ANALYZING:
            self.start_analysis_button.setText("Stop Analysis")
            self.start_analysis_button.setEnabled(True)
            self.request_move_button.setEnabled(False) # Cannot request move while analyzing
        elif state == EngineState.THINKING:
            self.start_analysis_button.setText("Start Analysis")
            self.start_analysis_button.setEnabled(False) # Cannot start analysis while thinking
            self.request_move_button.setEnabled(False) # Already thinking
        elif state == EngineState.IDLE:
            self.start_analysis_button.setText("Start Analysis")
            self.start_analysis_button.setEnabled(True)
            self.request_move_button.setEnabled(not self.board.is_game_over())
        elif state == EngineState.SHUTDOWN:
            self.start_analysis_button.setText("Start Analysis")
            self.start_analysis_button.setEnabled(False)
            self.request_move_button.setEnabled(False)

        # Also consider self.is_engine_thinking_ui_flag for immediate UI responsiveness
        # before state officially changes via timer.
        if self.is_engine_thinking_ui_flag: # True when request_best_move is called
             self.request_move_button.setEnabled(False)
             self.start_analysis_button.setEnabled(False)


    def handle_game_over(self):
        self.request_move_button.setEnabled(False)
        # Determine result
        if self.board.is_checkmate():
            msg = "Checkmate! " + ("White wins." if not self.board.turn else "Black wins.")
        elif self.board.is_stalemate():
            msg = "Stalemate! Draw."
        elif self.board.is_insufficient_material():
            msg = "Insufficient material! Draw."
        elif self.board.is_seventyfive_moves():
            msg = "75-move rule! Draw."
        elif self.board.is_fivefold_repetition():
            msg = "Fivefold repetition! Draw."
        else:
            msg = "Game over." # Other conditions

        QMessageBox.information(self, "Game Over", msg)
        self.status_label.setText(f"Status: {msg}")
        logger.info(f"Game over: {msg}. FEN: {self.board.fen()}")
        if self.engine_worker.get_state() == EngineState.ANALYZING:
            self.engine_worker.stop_analysis() # Stop analysis if game over
            self.update_ui_from_engine_state()


    def closeEvent(self, event):
        logger.info("Close event triggered for MainWindow.")
        if self.engine_worker:
            current_state = self.engine_worker.get_state()
            logger.info(f"Engine state on close: {current_state}")
            if current_state == EngineState.ANALYZING:
                logger.info("Stopping analysis before quitting...")
                # stop_analysis is blocking, which is fine for closeEvent
                self.engine_worker.stop_analysis()
                logger.info("Analysis stopped.")

            logger.info("Quitting engine worker...")
            self.engine_worker.quit_engine() # This method joins the worker thread
            logger.info("Engine worker quit.")

        self.ui_update_timer.stop()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Determine engine path (example: use "stockfish" if in PATH, or provide full path)
    # This should be configured properly in a real application
    engine_executable = "stockfish"
    # For development, you might pass it as an argument or use a config file
    # e.g., if len(sys.argv) > 1: engine_executable = sys.argv[1]

    main_win = MainWindow(engine_path=engine_executable)
    main_win.show()
    sys.exit(app.exec()) # Changed app.exec_() to app.exec() for PySide6

# Notes for further refinement:
# 1. Real-time analysis display: EngineWorker needs to be modified to stream analysis data
#    (e.g., via a queue or by emitting Qt signals through a helper object passed to it).
#    Then, `handle_engine_analysis` would update the UI with this live data.
# 2. Non-blocking engine moves: `request_engine_move_clicked` currently blocks the UI.
#    This should be moved to a separate QThread that, upon completion, emits a signal
#    with the best move. MainWindow would have a slot for this signal.
# 3. User moves: Implement a way for the user to make moves on the board (e.g., by clicking squares
#    or entering UCI moves). This would involve more complex event handling on the board display.
# 4. Configuration: Engine path and other settings should be configurable.
# 5. Error Handling: More robust error handling for engine communication issues.
# 6. SVG Board: Replace QTextEdit board display with a proper SVG rendering (e.g., using chess.svg
#    and QSvgWidget or QWebView/QWebEngineView).
# 7. Thread safety: Ensure all interactions with EngineWorker that modify shared state or UI
#    are handled correctly, especially if EngineWorker becomes more asynchronous with signals.
#    Direct calls from UI to EngineWorker that block (like current request_best_move) are simpler
#    but make UI less responsive. Checking state via timer is one way to decouple.
