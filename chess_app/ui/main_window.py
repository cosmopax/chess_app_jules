import sys
import logging
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QTextEdit,
    QLabel,
    QAction,
    QMessageBox,
    QInputDialog,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QObject
import random
import chess
import chess.svg
import chess.polyglot
import chess.openings
from chess_app.ui.chess_clock import ChessClock

# Assuming EngineWorker is in chess_app.engine.engine_worker
# Adjust the import path if your project structure is different.
from chess_app.engine.engine_worker import EngineWorker, EngineState

# Configure logging for this module. Root logger is configured in main.py.
logger = logging.getLogger(__name__)

class MainWindowSignals(QObject):
    """
    Defines custom signals for MainWindow.
    Useful for communication from non-GUI threads (like EngineWorker callbacks, if they were used)
    to the GUI thread in a Qt-safe manner.
    """
    # Example: Emitted when new analysis data is available from a background thread.
    analysis_update_ready = Signal(dict)
    # Example: Emitted when the engine has found a best move in a background thread.
    best_move_ready = Signal(chess.Move)
    # Example: Emitted when the engine worker's state changes (could be from worker thread).
    engine_state_changed_signal = Signal(EngineState)

class MainWindow(QMainWindow):
    """
    The main application window for the Chess AI Interface.
    Manages the UI elements, user interactions, and communication with the EngineWorker.
    """
    def __init__(self, engine_path: str = "stockfish"):
        super().__init__()
        self.setWindowTitle("Chess AI Interface")
        self.setGeometry(100, 100, 800, 700) # Adjusted height slightly for more room

        self.board = chess.Board() # The main chess board state
        self.engine_worker: EngineWorker | None = None  # Will be initialized later
        self.engine_path: str = engine_path

        self.clock = ChessClock(initial_seconds=300) # Default 5 minutes per side
        self.clock.time_changed.connect(self.update_clock_labels)

        # UI state flags: These flags help manage UI element enabled/disabled states
        # and reflect the user's perception of the engine's activity.
        # `is_engine_thinking_ui_flag` is set True when `request_engine_move_clicked` is called
        # and False when the (blocking) call returns. It helps `update_ui_elements` to immediately
        # disable buttons while the engine is thinking, even before the EngineWorker state formally changes.
        self.is_engine_thinking_ui_flag: bool = False
        # `analysis_is_on_ui_flag` is primarily updated by `update_ui_from_engine_state` based on
        # the EngineWorker's actual state. It reflects if analysis mode is active.
        self.analysis_is_on_ui_flag: bool = False

        self._init_ui()      # Initialize all UI components
        self._create_menu()  # Create the main menu bar
        self.reset_board()   # Set up the initial board state

        try:
            logger.info(f"MainWindow: Initializing EngineWorker with path: {self.engine_path}")
            self.engine_worker = EngineWorker(engine_path=self.engine_path)
        except Exception as e:
            logger.critical(f"MainWindow: Failed to initialize EngineWorker: {e}", exc_info=True)
            QMessageBox.critical(self, "Engine Initialization Error",
                                 f"Failed to initialize the chess engine from path '{self.engine_path}'.\n"
                                 f"Error: {e}\n\n"
                                 "Please ensure the engine is correctly installed and the path is valid. "
                                 "Engine-related features will be disabled.")
            # Disable engine-dependent UI elements if engine worker fails to initialize
            if hasattr(self, 'start_analysis_button'): self.start_analysis_button.setEnabled(False)
            if hasattr(self, 'request_move_button'): self.request_move_button.setEnabled(False)

        # This timer periodically calls `update_ui_from_engine_state` to refresh the UI
        # based on the current state of the EngineWorker and to poll for new analysis info.
        self.ui_update_timer = QTimer(self)
        self.ui_update_timer.timeout.connect(self.update_ui_from_engine_state)
        self.ui_update_timer.start(500) # Update interval: 500ms

        self.signals = MainWindowSignals()
        # Example connections (currently not used as EngineWorker uses direct calls/polling):
        # self.signals.analysis_update_ready.connect(self.handle_engine_analysis_signal)
        # self.signals.best_move_ready.connect(self.handle_engine_move_signal)
        # self.signals.engine_state_changed_signal.connect(self.on_engine_state_changed_signal)

        logger.info("MainWindow initialized.")

    def _init_ui(self):
        """Initializes the main UI layout and widgets."""
        logger.debug("MainWindow: Initializing UI components.")
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Chess board display (simple text for now, could be SVG or QGraphicsView)
        self.board_display = QTextEdit()
        self.board_display.setReadOnly(True)
        self.board_display.setFontFamily("monospace") # Monospace font for better text board alignment
        self.board_display.setFontPointSize(14)
        self.layout.addWidget(self.board_display)
        self.update_board_display() # Initial board display

        # Analysis display
        self.analysis_display = QTextEdit()
        self.analysis_display.setReadOnly(True)
        self.analysis_display.setFixedHeight(100)
        self.analysis_display.setFontFamily("monospace")
        self.layout.addWidget(self.analysis_display)

        # Opening info
        self.opening_label = QLabel("Opening: -")
        self.layout.addWidget(self.opening_label)
        self.opening_line_label = QLabel("Line: -") # Label for mainline moves
        self.layout.addWidget(self.opening_line_label)

        # Clocks
        self.white_clock_label = QLabel("White: 00:00") # Initialized by reset_board -> clock.reset
        self.black_clock_label = QLabel("Black: 00:00")
        self.layout.addWidget(self.white_clock_label)
        self.layout.addWidget(self.black_clock_label)

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
        logger.debug("MainWindow: UI components initialized.")

    def _create_menu(self):
        """Creates the main menu bar and its actions."""
        logger.debug("MainWindow: Creating menu bar.")
        self.menubar = self.menuBar()
        file_menu = self.menubar.addMenu("&File")

        new_game_action = QAction("New Standard Game", self)
        new_game_action.triggered.connect(self.new_standard_game)
        file_menu.addAction(new_game_action)

        new_960_random_action = QAction("New Chess960 (Random)", self)
        new_960_random_action.triggered.connect(self.new_chess960_random)
        file_menu.addAction(new_960_random_action)

        new_960_select_action = QAction("New Chess960 (Choose Position)...", self)
        new_960_select_action.triggered.connect(self.new_chess960_select)
        file_menu.addAction(new_960_select_action)

        file_menu.addSeparator()

        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close) # QMainWindow.close() triggers closeEvent
        file_menu.addAction(exit_action)
        logger.debug("MainWindow: Menu bar created.")

    def new_standard_game(self):
        """Starts a new standard chess game."""
        logger.info("MainWindow: Starting new standard game.")
        self.reset_board()

    def new_chess960_random(self):
        """Starts a new Chess960 game with a random start position."""
        logger.info("MainWindow: Starting new random Chess960 game.")
        self.reset_board(chess960=True)

    def new_chess960_select(self):
        """Prompts the user for a Chess960 start position and starts a new game."""
        logger.info("MainWindow: Prompting for Chess960 start position.")
        pos, ok = QInputDialog.getInt(
            self, "Chess960 Position", "Enter start position number (0-959):",
            0, 0, 959, 1
        )
        if ok:
            logger.info(f"MainWindow: Starting new Chess960 game with position: {pos}")
            self.reset_board(chess960=True, start_pos=pos)
        else:
            logger.info("MainWindow: Chess960 position selection cancelled.")

    def update_board_display(self):
        """Updates the text-based chess board display and opening information."""
        # For a real application, chess.svg.board or a custom QGraphicsScene would be used.
        logger.debug("MainWindow: Updating board display.")
        self.board_display.setText(str(self.board)) # Simple text representation
        self.update_opening_info()

    def reset_board(self, chess960: bool = False, start_pos: int | None = None):
        """Resets the board to the initial state (standard or Chess960)."""
        logger.info(f"MainWindow: Resetting board. Chess960: {chess960}, Start Position: {start_pos if start_pos is not None else 'Random' if chess960 else 'N/A'}")
        if self.engine_worker and self.engine_worker.get_state() == EngineState.ANALYZING:
            logger.info("MainWindow: Board reset requested while analysis was on. Stopping analysis first.")
            # This is a blocking call. If analysis doesn't stop quickly, UI might briefly hang.
            # Consider disabling reset button while analysis is stopping if this becomes an issue.
            if not self.engine_worker.stop_analysis():
                logger.warning("MainWindow: Analysis did not confirm stop during board reset. Proceeding with reset.")

        if chess960:
            if start_pos is None: # If no specific position, pick one randomly for Chess960
                start_pos = random.randint(0, 959)
            self.board = chess.Board.from_chess960_pos(start_pos)
            logger.info(f"MainWindow: Chess960 board created with start position: {start_pos}, FEN: {self.board.fen()}")
        else:
            self.board.reset()
            logger.info(f"MainWindow: Standard board reset. FEN: {self.board.fen()}")

        self.clock.reset() # Reset clock times
        self.clock.start(self.board.turn) # Start clock for the current player
        self.update_board_display() # Update visual board
        self.analysis_display.clear() # Clear any old analysis
        self.status_label.setText("Status: Board Reset. White's turn.")
        self.is_engine_thinking_ui_flag = False # Reset UI thinking flag
        self.update_ui_from_engine_state() # Refresh UI elements based on new state (should be IDLE)
        logger.info("MainWindow: Board reset complete.")


    def toggle_analysis_clicked(self):
        """Handles the click event for the 'Start/Stop Analysis' button."""
        if not self.engine_worker or not self.engine_worker.engine:
            logger.warning("MainWindow: Toggle analysis clicked but engine worker or engine not available.")
            QMessageBox.warning(self, "Engine Not Ready", "The chess engine is not available or not initialized.")
            return

        current_state = self.engine_worker.get_state()
        logger.info(f"MainWindow: Toggle analysis clicked. Current engine state: {current_state.name}")

        if current_state == EngineState.ANALYZING:
            self.status_label.setText("Status: Stopping analysis...")
            QApplication.processEvents() # Allow UI to update before blocking call
            # stop_analysis() is blocking. UI will be unresponsive until it returns.
            stopped_cleanly = self.engine_worker.stop_analysis()
            if not stopped_cleanly:
                logger.warning("MainWindow: Analysis stop command timed out or failed to confirm.")
                QMessageBox.warning(self, "Analysis Stop Issue",
                                    "The analysis engine did not confirm stopping in the expected time. "
                                    "Its state may be inconsistent.")
            else:
                logger.info("MainWindow: Analysis stopped successfully via UI toggle.")
            # UI state will be fully updated by update_ui_from_engine_state timer or explicitly below.
        elif current_state == EngineState.IDLE:
            logger.info("MainWindow: Requesting to start analysis via UI toggle.")
            self.status_label.setText("Status: Starting analysis...")
            # Make a copy of the board for the engine to analyze.
            self.engine_worker.start_analysis(self.board.copy())
            # analysis_is_on_ui_flag will be updated by update_ui_from_engine_state
        else: # THINKING or SHUTDOWN
            logger.warning(f"MainWindow: Cannot toggle analysis. Engine is busy ({current_state.name}) or shutdown.")
            QMessageBox.information(self, "Engine Busy or Offline",
                                    f"The engine is currently {current_state.name}. Cannot toggle analysis now.")

        self.update_ui_from_engine_state() # Explicitly update UI to reflect immediate state change intentions.

    def request_engine_move_clicked(self):
        # --- UI Responsiveness Note ---
        # The current implementation of self.engine_worker.request_best_move() is a blocking call.
        # This means that while the engine is thinking, the UI will freeze. This is especially
        # noticeable with longer thinking times.
        #
        # Recommended Approach: Move Engine Call to a Separate QThread
        # To keep the UI responsive, the engine's move calculation should be performed in a
        # separate worker thread. This involves the following general steps:
        #
        # 1. Create a QObject Worker Class:
        #    - Define a new class that inherits from QObject (e.g., `EngineMoveWorker`).
        #    - This class will have a method (e.g., `calculate_move(board, time_limit)`)
        #      that calls `self.engine_worker.request_best_move(board, time_limit)`.
        #    - The worker method should emit a Qt signal (e.g., `move_ready = Signal(chess.Move)`)
        #      when the engine returns the move, or another signal for errors/no move.
        #
        # 2. In `request_engine_move_clicked` (this method):
        #    a. Instantiate the `EngineMoveWorker`.
        #    b. Create a new `QThread` instance.
        #    c. Move the `EngineMoveWorker` instance to the `QThread` using `worker.moveToThread(thread)`.
        #    d. Connect the `EngineMoveWorker`'s `move_ready` signal to a slot in `MainWindow`
        #       (e.g., `handle_engine_move_from_thread(move)`). This slot would then typically
        #       call the existing `self.handle_engine_move(move)` logic.
        #    e. Connect the `QThread`'s `started` signal to the `EngineMoveWorker`'s `calculate_move` method.
        #       This ensures the worker method runs when the thread starts.
        #    f. Connect the `QThread`'s `finished` signal to perform cleanup actions, such as
        #       calling `deleteLater()` on both the thread and the worker to free resources.
        #       Also, handle any UI updates needed when the thread finishes (e.g., re-enabling buttons
        #       if not handled by the move_ready signal).
        #    g. Start the thread using `thread.start()`.
        #    h. Disable UI elements (e.g., "Request Engine Move" button) to prevent multiple requests
        #       while the thread is running. Re-enable them in the slot connected to `move_ready`
        #       or `finished`.
        #
        # 3. Implement the Slot for Handling the Move:
        #    - The `handle_engine_move_from_thread(move)` slot in `MainWindow` would receive the
        #      `chess.Move` object from the worker's signal.
        #    - This slot would then call `self.handle_engine_move(move)` to update the board and UI.
        #
        # This refactoring is crucial for maintaining a responsive user interface, especially
        # when the engine requires significant time to calculate the best move.
        # --- End UI Responsiveness Note ---

        if not self.engine_worker or not self.engine_worker.engine:
            logger.warning("MainWindow: Request engine move clicked, but engine worker or engine not available.")
            QMessageBox.warning(self, "Engine Not Ready", "The chess engine is not available or not initialized.")
            return

        if self.board.is_game_over():
            logger.info("MainWindow: Request engine move clicked, but game is over.")
            QMessageBox.information(self, "Game Over", "The game is over. Cannot request a new move.")
            return

        current_state = self.engine_worker.get_state()
        if current_state == EngineState.IDLE:
            logger.info(f"MainWindow: Requesting engine move for FEN: {self.board.fen()}")
            self.status_label.setText(f"Status: Engine ({self.engine_path}) is thinking...")
            self.is_engine_thinking_ui_flag = True # UI perception: engine is busy with our request.
            self.update_ui_elements() # Immediately disable buttons.
            QApplication.processEvents() # Ensure UI updates before blocking call.

            # This is a BLOCKING call to EngineWorker, which itself blocks waiting for the engine.
            # The UI will freeze during this time.
            time_limit_s = 1.0 # Example: 1 second thinking time. Configurable in a real app.
            move = self.engine_worker.request_best_move(self.board.copy(), time_limit_s)

            self.is_engine_thinking_ui_flag = False # Engine has finished or failed.
            if move:
                logger.info(f"MainWindow: Engine returned move: {move.uci()}. Applying to board.")
                self.handle_engine_move(move)
            else:
                logger.warning("MainWindow: Engine did not return a move or an error occurred.")
                QMessageBox.warning(self, "No Move Returned",
                                    "The engine did not return a move. This could be due to an internal engine error or timeout.")
                self.status_label.setText("Status: Idle. Engine failed to find a move.")

            # update_ui_elements() will be called by update_ui_from_engine_state,
            # but calling it here ensures UI is responsive if the state timer is slow.
            self.update_ui_elements()
            self.update_ui_from_engine_state() # Refresh state display fully.
        else: # ANALYZING, THINKING (shouldn't happen if UI is correctly disabled), or SHUTDOWN
            logger.warning(f"MainWindow: Cannot request engine move. Engine is busy ({current_state.name}) or shutdown.")
            QMessageBox.information(self, "Engine Busy or Offline",
                                    f"The engine is currently {current_state.name}. Cannot request a move now.")


    def handle_engine_move(self, move: chess.Move):
        """
        Applies a valid engine move to the board and updates the UI.
        Called after request_engine_move_clicked receives a move.
        """
        if move and move in self.board.legal_moves:
            logger.info(f"MainWindow: Applying engine move: {move.uci()} to board FEN: {self.board.fen()}")
            self.board.push(move)
            self.update_board_display()
            current_player_turn = "White" if self.board.turn == chess.WHITE else "Black"
            self.status_label.setText(f"Status: Engine played {move.uci()}. {current_player_turn}'s turn.")
            self.clock.switch() # Switch active player on clock
            if not self.board.is_game_over():
                self.clock.start(self.board.turn) # Start clock for the next player
            else: # Game is over
                self.clock.stop()
                self.handle_game_over()
        elif move: # Engine returned a move, but it's illegal for the current position
            logger.error(f"MainWindow: Engine returned an ILLEGAL move: {move.uci()} for board FEN: {self.board.fen()}")
            QMessageBox.critical(self, "Illegal Engine Move",
                                 f"The engine suggested an illegal move: {move.uci()}.\n"
                                 "This may indicate an issue with the engine or internal board state. Please report this.")
            self.status_label.setText(f"Status: Engine suggested illegal move {move.uci()}. Please reset.")
        else: # move is None, this case should ideally be handled by the caller.
            logger.warning("MainWindow: handle_engine_move called with no move (None).")
            # Status label already set by request_engine_move_clicked's error handling.
            pass

        self.update_ui_elements() # Refresh button states, etc.

    def handle_engine_analysis(self, analysis_data: dict | None):
        """
        Displays analysis information (score, PV) received from the EngineWorker.
        Called by `update_ui_from_engine_state` when analysis info is available.
        """
        if not analysis_data: # Clear display if no data (e.g., analysis stopped)
            # logger.debug("MainWindow: No analysis data to display, clearing analysis text.")
            self.analysis_display.clear()
            return

        # Example: analysis_data might be {'score': PovScore(Cp(+102), WHITE), 'pv': [Move.from_uci('e2e4'), ...]}
        score_obj = analysis_data.get("score")
        pv_moves = analysis_data.get("pv")
        depth = analysis_data.get("depth", "-") # Get depth, default to '-'
        seldepth = analysis_data.get("seldepth", "-") # Get selective depth
        nodes = analysis_data.get("nodes", 0) # Get nodes searched
        nps = analysis_data.get("nps", 0) # Get nodes per second

        text_parts = []
        if score_obj is not None:
            # Format score based on type (Cp or Mate)
            if score_obj.is_mate():
                mate_in = score_obj.mate()
                score_str = f"Mate in {mate_in}" if mate_in is not None else "Mate (unknown)"
            else: # Centipawn score
                cp_score = score_obj.relative.score(mate_score=10000) # Get centipawn value
                score_str = f"{cp_score / 100.0:.2f}" if cp_score is not None else "N/A"
            text_parts.append(f"Score: {score_str}")

        if pv_moves:
            # Convert PV moves to UCI strings for display
            pv_str = " ".join(move.uci() for move in pv_moves)
            text_parts.append(f"PV: {pv_str}")

        text_parts.append(f"Depth: {depth}/{seldepth}")
        text_parts.append(f"Nodes: {nodes:,} ({nps:,} nps)") # Formatted numbers

        self.analysis_display.setText(" | ".join(text_parts))
        # logger.debug(f"MainWindow: Displayed analysis: {' | '.join(text_parts)}")


    def update_ui_from_engine_state(self):
        """
        Updates various UI elements based on the current state of the EngineWorker.
        This method is called periodically by `ui_update_timer`.
        """
        # logger.debug("MainWindow: Polling EngineWorker state for UI update.")
        if not self.engine_worker:
            self.status_label.setText("Status: Engine worker not available.")
            self.start_analysis_button.setEnabled(False)
            self.request_move_button.setEnabled(False)
            return

        state = self.engine_worker.get_state()
        # logger.debug(f"MainWindow: Current EngineWorker state: {state.name}")

        # Update UI flags based on the actual engine state.
        # These flags help `update_ui_elements` make decisions.
        self.analysis_is_on_ui_flag = (state == EngineState.ANALYZING)
        # self.is_engine_thinking_ui_flag is managed by request_engine_move_clicked directly
        # because request_best_move is blocking. If it were non-blocking, this is where
        # is_engine_thinking_ui_flag would be set based on EngineState.THINKING.

        if state == EngineState.IDLE:
            self.status_label.setText(f"Status: Engine Idle. {self.board.turn == chess.WHITE and 'White' or 'Black'}'s turn.")
            if not self.analysis_is_on_ui_flag: # Clear analysis only if truly idle and not just between analysis updates
                 self.analysis_display.clear()
        elif state == EngineState.ANALYZING:
            self.status_label.setText("Status: Engine Analyzing...")
            # Poll for the latest analysis information from EngineWorker
            info = self.engine_worker.get_latest_analysis_info()
            self.handle_engine_analysis(info) # Update the analysis display
        elif state == EngineState.THINKING:
            # This state is usually very brief if request_best_move is blocking,
            # as status_label is set directly in request_engine_move_clicked.
            # However, if request_best_move were non-blocking, this would be the primary update.
            self.status_label.setText("Status: Engine Thinking...")
        elif state == EngineState.SHUTDOWN:
            self.status_label.setText("Status: Engine Offline or Error. Please check configuration or restart.")
            self.analysis_display.setText("Engine is offline.")
        else: # Should not happen
            logger.warning(f"MainWindow: Encountered unknown engine state: {state.name}")
            self.status_label.setText(f"Status: Unknown Engine State ({state.name})")

        self.update_ui_elements() # Adjust button enabled/disabled states, text, etc.

    def update_ui_elements(self):
        """
        Updates the state of UI elements (buttons, etc.) based on the application's
        current state (board state, engine worker state, UI flags).
        """
        # logger.debug("MainWindow: Updating UI element states.")
        if not self.engine_worker or not self.engine_worker.engine:
            self.start_analysis_button.setText("Start Analysis")
            self.start_analysis_button.setEnabled(False)
            self.request_move_button.setEnabled(False)
            # logger.debug("MainWindow: Engine worker or engine not available, disabling engine buttons.")
            return

        engine_state = self.engine_worker.get_state()
        game_over = self.board.is_game_over()

        # --- Start/Stop Analysis Button ---
        if engine_state == EngineState.ANALYZING:
            self.start_analysis_button.setText("Stop Analysis")
            self.start_analysis_button.setEnabled(True)
        elif engine_state == EngineState.IDLE:
            self.start_analysis_button.setText("Start Analysis")
            self.start_analysis_button.setEnabled(not game_over and not self.is_engine_thinking_ui_flag)
        elif engine_state == EngineState.THINKING or self.is_engine_thinking_ui_flag: # Engine is busy thinking
            self.start_analysis_button.setText("Start Analysis")
            self.start_analysis_button.setEnabled(False)
        elif engine_state == EngineState.SHUTDOWN:
            self.start_analysis_button.setText("Start Analysis (Offline)")
            self.start_analysis_button.setEnabled(False)

        # --- Request Engine Move Button ---
        can_request_move = (engine_state == EngineState.IDLE and
                            not game_over and
                            not self.analysis_is_on_ui_flag and # Typically, don't request move if analysis is on
                            not self.is_engine_thinking_ui_flag)
        self.request_move_button.setEnabled(can_request_move)

        # --- Reset Board Button ---
        # Usually always enabled, unless we want to prevent reset during critical operations.
        # For now, allow reset even if engine is busy (reset_board handles stopping analysis).
        self.reset_board_button.setEnabled(True)

        # logger.debug(f"MainWindow: UI elements updated. AnalysisBtn: {self.start_analysis_button.isEnabled()}, MoveBtn: {self.request_move_button.isEnabled()}")


    def handle_game_over(self):
        """Handles UI updates when the game ends."""
        logger.info(f"MainWindow: Game over detected. Board FEN: {self.board.fen()}")
        self.request_move_button.setEnabled(False) # Disable requesting more moves
        self.clock.stop() # Stop the game clock

        # Determine and display the game result
        if self.board.is_checkmate():
            winner = "Black" if self.board.turn == chess.WHITE else "White" # Winner is whose turn it is NOT
            msg = f"Checkmate! {winner} wins."
        elif self.board.is_stalemate():
            msg = "Stalemate! Draw."
        elif self.board.is_insufficient_material():
            msg = "Insufficient material! Draw."
        elif self.board.is_seventyfive_moves():
            msg = "75-move rule! Draw."
        elif self.board.is_fivefold_repetition():
            msg = "Fivefold repetition! Draw."
        elif self.board.is_variant_draw() or self.board.is_variant_loss() or self.board.is_variant_win():
            # Specific to chess variants, but good to have for completeness
            msg = "Game over by variant-specific rule."
        else: # Should not happen if game_over is true based on standard rules
            msg = "Game over."
            logger.warning(f"MainWindow: Game is over, but specific reason not matched by standard checks. Result: {self.board.result()}")


        QMessageBox.information(self, "Game Over", msg)
        self.status_label.setText(f"Status: {msg}")
        logger.info(f"MainWindow: Game ended with message: {msg}")

        # If analysis was running when game ended, stop it.
        if self.engine_worker and self.engine_worker.get_state() == EngineState.ANALYZING:
            logger.info("MainWindow: Game over, stopping analysis.")
            self.engine_worker.stop_analysis() # This is blocking
            self.update_ui_from_engine_state() # Refresh UI after stopping analysis

    def update_clock_labels(self, white_seconds: int, black_seconds: int):
        """Updates the clock display labels."""
        def format_time(seconds: int) -> str:
            m, s = divmod(max(0, seconds), 60) # Ensure seconds is not negative
            return f"{m:02d}:{s:02d}"

        self.white_clock_label.setText(f"White: {format_time(white_seconds)}")
        self.black_clock_label.setText(f"Black: {format_time(black_seconds)}")
        # logger.debug(f"MainWindow: Clock labels updated - White: {white_seconds}s, Black: {black_seconds}s")

    def update_opening_info(self):
        """Updates labels with information about the current chess opening using polyglot."""
        # This can be slow if the opening book is large or accessed frequently.
        # Consider moving to a background thread if performance issues arise.
        logger.debug("MainWindow: Updating opening information.")
        try:
            # Try to find the opening name from the polyglot book
            opening_name = chess.polyglot.opening_name(self.board)
        except IndexError: # Can happen if board position is not in book or book is empty/not found
            opening_name = "Unknown Opening"
            logger.debug("MainWindow: Opening name not found in polyglot book (IndexError).")
        except Exception as e: # Catch other potential errors from polyglot
            opening_name = "Error finding opening"
            logger.warning(f"MainWindow: Error accessing polyglot opening name: {e}", exc_info=True)

        self.opening_label.setText(f"Opening: {opening_name}")

        # Try to find the ECO (Encyclopaedia of Chess Openings) code and name
        try:
            opening_eco = chess.openings.Opening(self.board) # This finds the best match
            eco_code = opening_eco.eco()
            eco_name = opening_eco.name()
            # Mainline moves for the identified opening
            # mainline = " ".join(m.uci() for m in opening_eco.mainline()) if opening_eco.mainline() else ""
            # self.opening_line_label.setText(f"ECO: {eco_code} ({eco_name}) Line: {mainline}")
            self.opening_line_label.setText(f"ECO: {eco_code} - {eco_name}")

        except Exception as e: # chess.openings might raise errors if position is too deep or unusual
            self.opening_line_label.setText("ECO: -")
            logger.debug(f"MainWindow: Could not determine ECO opening: {e}")

        # logger.debug(f"MainWindow: Opening info updated - Name: {opening_name}, ECO: {self.opening_line_label.text()}")


    def closeEvent(self, event):
        """Handles the window close event to ensure graceful shutdown of the engine worker."""
        logger.info("MainWindow: Close event triggered.")
        if self.engine_worker:
            current_engine_state = self.engine_worker.get_state()
            logger.info(f"MainWindow: Engine state on close: {current_engine_state.name}")

            # If analysis is running, attempt to stop it first.
            if current_engine_state == EngineState.ANALYZING:
                logger.info("MainWindow: Stopping analysis before quitting...")
                # engine_worker.stop_analysis() is blocking, which is generally acceptable
                # during a close event as the application is shutting down.
                if not self.engine_worker.stop_analysis(): # Timeout is handled in stop_analysis
                    logger.warning("MainWindow: Timeout or issue stopping analysis during close event. Proceeding with quit.")
                else:
                    logger.info("MainWindow: Analysis stopped.")

            logger.info("MainWindow: Quitting engine worker...")
            # engine_worker.quit_engine() is also blocking and ensures the worker thread is joined.
            self.engine_worker.quit_engine()
            logger.info("MainWindow: Engine worker quit command issued and thread joined.")
        else:
            logger.info("MainWindow: No engine worker instance to quit.")

        self.ui_update_timer.stop() # Stop the UI update timer
        logger.info("MainWindow: UI update timer stopped.")
        event.accept() # Accept the close event
        logger.info("MainWindow: Close event accepted. Application will exit.")


if __name__ == '__main__':
    # This block is for testing/running MainWindow directly.
    # Ensure logging is configured for this standalone run.
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    app = QApplication(sys.argv)

    # Determine engine path (e.g., "stockfish" if in PATH, or provide full path)
    # This should ideally be handled by a configuration mechanism in a real application.
    engine_executable_path = "stockfish"
    # Example for developers: pass engine path as a command-line argument
    # if len(sys.argv) > 1: engine_executable_path = sys.argv[1]
    logger.info(f"Example Main: Using engine path: {engine_executable_path}")

    main_window = MainWindow(engine_path=engine_executable_path)
    main_window.show()
    sys.exit(app.exec()) # Use app.exec() for PySide6

# Notes for further refinement (some of these are substantial features):
# 1. Real-time analysis display: For smoother updates, EngineWorker could emit Qt signals
#    with analysis data rather than relying purely on polling via `get_latest_analysis_info`.
#    MainWindow would then have a slot connected to this signal.
# 2. User moves: Implement a way for the user to make moves on the board (e.g., by clicking squares
#    or entering UCI moves). This is a major UI development task.
# 3. Configuration: Engine path, thinking time, clock settings, etc., should be configurable
#    through the UI (e.g., a settings dialog) and persisted.
# 4. Error Handling: More granular error handling and user feedback for engine communication issues
#    (e.g., if engine crashes post-initialization).
# 5. SVG Board: Replace the QTextEdit board display with a proper SVG rendering using chess.svg
#    and QSvgWidget or a QGraphicsView for a much better visual experience and interactivity.
# 6. Polyglot Opening Book: Ensure a polyglot opening book (e.g., "book.bin") is available
#    for the opening name feature to work effectively. Path to book could be configurable.
# 7. Thread safety: While current interactions are mostly from UI to worker thread (queued) or polling,
#    if EngineWorker becomes more asynchronous with signals back to UI, ensure all cross-thread
#    interactions are Qt-safe (e.g., emitting signals, using QMetaObject.invokeMethod if needed).
