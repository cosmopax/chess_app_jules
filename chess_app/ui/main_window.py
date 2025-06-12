import datetime
import logging
import os  # For os.path.basename in status message
import random

import chess
import chess.openings
import chess.pgn
import chess.polyglot
import chess.svg
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QAction,
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chess_app.engine.engine_worker import EngineState, EngineWorker
from chess_app.openings import fetch_lichess_moves
from chess_app.ui.chat_window import ChatWindow
from chess_app.ui.chess_clock import ChessClock

logger = logging.getLogger(__name__)


class OpeningExplorerDialog(QDialog):
    opening_selected_for_practice = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Opening Explorer")
        self.setMinimumSize(600, 400)
        self.layout = QVBoxLayout(self)
        self.openings_list_widget = QListWidget()
        self.populate_openings()
        self.openings_list_widget.currentItemChanged.connect(self.on_opening_selected)
        self.layout.addWidget(self.openings_list_widget)
        self.details_layout = QVBoxLayout()
        self.eco_label = QLabel("ECO: -")
        self.name_label = QLabel("Name: -")
        self.mainline_label = QLabel("Mainline Moves (UCI):")
        self.mainline_display = QTextEdit()
        self.mainline_display.setReadOnly(True)
        self.mainline_display.setFixedHeight(80)
        self.details_layout.addWidget(self.eco_label)
        self.details_layout.addWidget(self.name_label)
        self.details_layout.addWidget(self.mainline_label)
        self.details_layout.addWidget(self.mainline_display)
        self.layout.addLayout(self.details_layout)
        self.button_box = QHBoxLayout()
        self.practice_button = QPushButton("Practice This Opening")
        self.practice_button.clicked.connect(self.on_practice_opening)
        self.practice_button.setEnabled(False)
        self.button_box.addWidget(self.practice_button)
        self.button_box.addStretch()
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        self.button_box.addWidget(self.close_button)
        self.layout.addLayout(self.button_box)
        if self.openings_list_widget.count() > 0:
            self.openings_list_widget.setCurrentRow(0)

    def populate_openings(self):
        try:
            if not chess.openings.ECO_OPENINGS:
                self.openings_list_widget.addItem("No openings found.")
                return
            for opening_obj in chess.openings.ECO_OPENINGS:
                display_text = f"{opening_obj.eco()} {opening_obj.name()}"
                list_item = QListWidgetItem(display_text)
                list_item.setData(Qt.UserRole, opening_obj)
                self.openings_list_widget.addItem(list_item)
        except Exception as e:
            self.openings_list_widget.addItem(f"Error: {e}")

    def on_opening_selected(self, current_item, previous_item):
        if not current_item:
            self.eco_label.setText("ECO: -")
            self.name_label.setText("Name: -")
            self.mainline_display.clear()
            self.practice_button.setEnabled(False)
            return
        opening_obj = current_item.data(Qt.UserRole)
        if isinstance(opening_obj, chess.openings.Opening):
            self.eco_label.setText(f"ECO: {opening_obj.eco()}")
            self.name_label.setText(f"Name: {opening_obj.name()}")
            self.mainline_display.setText(
                " ".join(m.uci() for m in opening_obj.mainline())
            )
            self.practice_button.setEnabled(True)
        else:
            self.eco_label.setText("ECO: Error")
            self.name_label.setText("Name: Error")
            self.mainline_display.clear()
            self.practice_button.setEnabled(False)

    def on_practice_opening(self):
        current_item = self.openings_list_widget.currentItem()
        if current_item:
            opening_obj = current_item.data(Qt.UserRole)
            if isinstance(opening_obj, chess.openings.Opening):
                self.opening_selected_for_practice.emit(opening_obj)
                self.accept()


class ClickableBoardWidget(QSvgWidget):
    clicked_square = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.player_color = chess.WHITE

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            square_width = self.width() / 8.0
            square_height = self.height() / 8.0
            x, y = event.pos().x(), event.pos().y()
            file_idx_visual, rank_idx_visual_from_top = int(x / square_width), int(
                y / square_height
            )
            if 0 <= file_idx_visual < 8 and 0 <= rank_idx_visual_from_top < 8:
                true_rank = (
                    (7 - rank_idx_visual_from_top)
                    if self.player_color == chess.WHITE
                    else rank_idx_visual_from_top
                )
                true_file = (
                    file_idx_visual
                    if self.player_color == chess.WHITE
                    else (7 - file_idx_visual)
                )
                self.clicked_square.emit(chess.square(true_file, true_rank))


class MainWindowSignals(QObject):
    analysis_update_ready = Signal(dict)
    best_move_ready = Signal(chess.Move)
    engine_state_changed_signal = Signal(EngineState)


class MainWindow(QMainWindow):
    def __init__(self, engine_path: str = "stockfish"):
        super().__init__()
        self.setWindowTitle("Chess AI Interface")
        self.setGeometry(100, 100, 800, 700)
        self.board = chess.Board()
        self.engine_worker: EngineWorker | None = None
        self.engine_path = engine_path
        self.player_color = chess.WHITE
        self.selected_square: chess.Square | None = None
        self.practice_opening_mainline = []
        self.current_practice_move_index = -1
        self.loaded_pgn_moves = []
        self.current_loaded_pgn_move_index = -1
        self.is_in_review_mode = False
        self.clock = ChessClock(initial_seconds=300)
        self.clock.time_changed.connect(self.update_clock_labels)
        self.is_engine_thinking_ui_flag = False
        self.analysis_is_on_ui_flag = False
        self._init_ui()
        self._create_menu()
        self.reset_board()
        try:
            self.engine_worker = EngineWorker(engine_path=self.engine_path)
        except Exception as e:
            QMessageBox.critical(self, "Engine Error", f"Failed to init engine: {e}")
        self.ui_update_timer = QTimer(self)
        self.ui_update_timer.timeout.connect(self.update_ui_from_engine_state)
        self.ui_update_timer.start(500)
        self.signals = MainWindowSignals()
        logger.info("MainWindow initialized.")

    def _init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.board_display = ClickableBoardWidget(self)
        self.board_display.setFixedSize(400, 400)
        self.board_display.player_color = self.player_color
        self.board_display.clicked_square.connect(self.handle_square_click)
        self.layout.addWidget(self.board_display)
        self.analysis_display = QTextEdit()
        self.analysis_display.setReadOnly(True)
        self.analysis_display.setFixedHeight(100)
        self.layout.addWidget(self.analysis_display)
        self.opening_label = QLabel("Opening: -")
        self.layout.addWidget(self.opening_label)
        self.opening_line_label = QLabel("Line: -")
        self.layout.addWidget(self.opening_line_label)
        self.lichess_moves_label = QLabel("Lichess: -")
        self.layout.addWidget(self.lichess_moves_label)
        self.white_clock_label = QLabel("White: 00:00")
        self.layout.addWidget(self.white_clock_label)
        self.black_clock_label = QLabel("Black: 00:00")
        self.layout.addWidget(self.black_clock_label)
        self.status_label = QLabel("Status: Initializing...")
        self.layout.addWidget(self.status_label)

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

        self.prev_mainline_move_button = QPushButton("<- Prev Mainline")
        self.prev_mainline_move_button.clicked.connect(self.show_previous_mainline_move)
        self.prev_mainline_move_button.setVisible(False)
        self.button_layout.addWidget(self.prev_mainline_move_button)

        self.next_mainline_move_button = QPushButton("Next Mainline ->")
        self.next_mainline_move_button.clicked.connect(self.show_next_mainline_move)
        self.next_mainline_move_button.setVisible(False)
        self.button_layout.addWidget(self.next_mainline_move_button)
        self.layout.addLayout(self.button_layout)

        self.pgn_button_layout = QHBoxLayout()
        self.prev_pgn_move_button = QPushButton("<- Prev PGN Move")
        self.prev_pgn_move_button.clicked.connect(self.pgn_show_previous_move)
        self.prev_pgn_move_button.setVisible(False)
        self.pgn_button_layout.addWidget(self.prev_pgn_move_button)

        self.next_pgn_move_button = QPushButton("Next PGN Move ->")
        self.next_pgn_move_button.clicked.connect(self.pgn_show_next_move)
        self.next_pgn_move_button.setVisible(False)
        self.pgn_button_layout.addWidget(self.next_pgn_move_button)

        self.layout.addLayout(self.pgn_button_layout)
        logger.debug("UI components initialized.")

    def _create_menu(self):
        self.menubar = self.menuBar()
        file_menu = self.menubar.addMenu("&File")

        # Sub-menu for New Game options
        new_game_menu = file_menu.addMenu("New Game")

        play_as_white_action = QAction("Play as White", self)
        play_as_white_action.triggered.connect(
            lambda: self.new_standard_game_as_color(chess.WHITE)
        )
        new_game_menu.addAction(play_as_white_action)

        play_as_black_action = QAction("Play as Black", self)
        play_as_black_action.triggered.connect(
            lambda: self.new_standard_game_as_color(chess.BLACK)
        )
        new_game_menu.addAction(play_as_black_action)

        new_game_menu.addSeparator()

        # Keep original "New Standard Game" for now, defaulting to White, or remove if redundant
        # For now, let's make it also call new_standard_game_as_color with WHITE
        new_std_game_direct_action = QAction("New Standard Game (Default White)", self)
        new_std_game_direct_action.triggered.connect(
            self.new_standard_game
        )  # new_standard_game will call ..._as_color
        # file_menu.addAction(new_std_game_direct_action) # Or add to new_game_menu

        actions = [
            # ("New Standard Game", self.new_standard_game), # Replaced by submenu
            ("New Chess960 (Random)", self.new_chess960_random),
            ("New Chess960 (Choose Position)...", self.new_chess960_select),
            ("Start From FEN...", self.new_from_fen),
            ("Load FEN From File...", self.load_fen_from_file),
            ("Load Game from PGN...", self.load_game_from_pgn),
            None,
            ("Save Game As PGN...", self.save_game_as_pgn),
            None,
            ("&Exit", self.close),
        ]
        for name, slot in actions:
            if name is None:
                file_menu.addSeparator()
                continue
            action = QAction(name, self)
            action.triggered.connect(slot)
            file_menu.addAction(action)
        tools_menu = self.menubar.addMenu("&Tools")
        explore_openings_action = QAction("Explore Openings...", self)
        explore_openings_action.triggered.connect(self.show_opening_explorer)
        tools_menu.addAction(explore_openings_action)

        chat_action = QAction("Open Chat...", self)
        chat_action.triggered.connect(self.show_chat_window)
        tools_menu.addAction(chat_action)
        logger.debug("Menu bar created.")

    def show_opening_explorer(self):
        dialog = OpeningExplorerDialog(self)
        dialog.opening_selected_for_practice.connect(
            self.handle_setup_opening_for_practice
        )
        dialog.exec()

    def show_chat_window(self):
        if not hasattr(self, "_chat_window") or self._chat_window is None:
            self._chat_window = ChatWindow(self)
        self._chat_window.show()

    def new_standard_game_as_color(self, player_chosen_color: bool):
        """Starts a new standard game with the player as the chosen color."""
        logger.info(
            f"MainWindow: Starting new standard game as {'White' if player_chosen_color == chess.WHITE else 'Black'}."
        )
        self.player_color = player_chosen_color
        if hasattr(self.board_display, "player_color"):  # Update ClickableBoardWidget
            self.board_display.player_color = self.player_color

        self.reset_board()  # This will set up a standard game, respecting self.player_color for display

        color_name = chess.COLOR_NAMES[self.player_color]
        self.status_label.setText(
            f"New game. Player is {color_name}. {'Your turn.' if self.player_color == chess.WHITE else 'White (AI) to move.'}"
        )

        if self.player_color == chess.BLACK and self.board.turn == chess.WHITE:
            logger.info("MainWindow: Player is Black, AI (White) makes the first move.")
            # Ensure UI updates before engine potentially blocks
            QTimer.singleShot(
                150, self.request_engine_move_clicked
            )  # Slightly longer delay for UI

    def new_standard_game(self):
        """Starts a new standard game, defaulting to player as White."""
        self.new_standard_game_as_color(chess.WHITE)

    def new_chess960_random(self):
        self.reset_board(chess960=True)  # TODO: Consider color choice for 960 too

    def new_chess960_select(self):
        pos, ok = QInputDialog.getInt(
            self, "Chess960 Position", "Enter (0-959):", 0, 0, 959, 1
        )
        if ok:
            self.reset_board(chess960=True, start_pos=pos)

    def update_board_display(self):
        last_move = self.board.peek() if self.board.move_stack else None
        fill_dict = (
            {self.selected_square: "#cc0000aa"}
            if self.selected_square is not None
            else {}
        )
        svg_bytes = chess.svg.board(
            self.board,
            orientation=self.player_color,
            lastmove=last_move,
            fill=fill_dict,
            size=400,
        ).encode("UTF-8")
        self.board_display.load(svg_bytes)
        self.update_opening_info()

    def reset_board(self, chess960: bool = False, start_pos: int | None = None):
        logger.info(f"Resetting board. Chess960: {chess960}, Start Pos: {start_pos}")
        if (
            self.engine_worker
            and self.engine_worker.get_state() == EngineState.ANALYZING
        ):
            self.engine_worker.stop_analysis()
        if chess960:
            self.board = chess.Board.from_chess960_pos(
                start_pos or random.randint(0, 959)
            )
        else:
            self.board.reset()
        self.clock.reset()
        self.clock.start(self.board.turn)
        self.selected_square = None
        self.end_opening_practice_mode()
        self.setup_pgn_review_mode(False)
        self.update_board_display()
        self.analysis_display.clear()
        self.status_label.setText("Status: Board Reset.")
        # After reset_board, if player is black and it's AI's turn, AI should move.
        # This is handled by new_standard_game_as_color. reset_board itself shouldn't trigger AI.
        self.update_ui_from_engine_state()

    def load_fen(self, fen: str):
        logger.info(f"Loading FEN: {fen}")
        try:
            new_board = chess.Board(fen)
        except Exception as e:
            QMessageBox.warning(self, "Invalid FEN", str(e))
            return
        if (
            self.engine_worker
            and self.engine_worker.get_state() == EngineState.ANALYZING
        ):
            self.engine_worker.stop_analysis()
        self.board = new_board
        self.clock.reset()
        self.clock.start(self.board.turn)
        self.selected_square = None
        self.end_opening_practice_mode()
        self.setup_pgn_review_mode(False)
        self.update_board_display()
        self.analysis_display.clear()
        self.status_label.setText("Status: Position loaded.")
        self.update_ui_from_engine_state()

    def new_from_fen(self):
        fen, ok = QInputDialog.getText(self, "Start From FEN", "Enter FEN string:")
        if ok and fen:
            self.load_fen(fen)

    def load_fen_from_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open FEN File", "", "FEN (*.fen);;All (*)"
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.load_fen(f.readline().strip())
            except Exception as e:
                QMessageBox.warning(self, "File Error", str(e))

    def toggle_analysis_clicked(self):
        if not self.engine_worker or not self.engine_worker.engine:
            QMessageBox.warning(self, "Engine Not Ready", "Engine not available.")
            return
        state = self.engine_worker.get_state()
        if state == EngineState.ANALYZING:
            # print("DEBUG_MW_TOGGLE: In ANALYZING block, attempting to stop.") # Manual debug
            self.status_label.setText("Status: Stopping analysis...")
            # print(f"DEBUG_MW_TOGGLE: status_label is {self.status_label} (id: {id(self.status_label)}) before stop setText") # Manual debug
            self.engine_worker.stop_analysis()
        elif state == EngineState.IDLE:
            # print("DEBUG_MW_TOGGLE: In IDLE block, attempting to start.") # Manual debug
            # print(f"DEBUG_MW_TOGGLE: status_label is {self.status_label} (id: {id(self.status_label)}) before start setText") # Manual debug
            self.status_label.setText("Status: Starting analysis...")
            # print("DEBUG_MW_TOGGLE: setText for Starting analysis CALLED in main_window.py") # Manual debug
            self.engine_worker.start_analysis(self.board.copy())
        else:
            # print(f"DEBUG_MW_TOGGLE: In ELSE block, state: {state.name}") # Manual debug
            QMessageBox.information(
                self, "Engine Busy", f"Engine is {state.name}. Cannot toggle analysis."
            )
        self.update_ui_from_engine_state()

    def request_engine_move_clicked(self):
        if self.is_in_review_mode:
            QMessageBox.information(
                self, "Review Mode", "Request engine move disabled during PGN review."
            )
            return
        if (
            not self.engine_worker
            or not self.engine_worker.engine
            or self.board.is_game_over()
            or self.engine_worker.get_state() != EngineState.IDLE
        ):
            QMessageBox.warning(
                self, "Engine Not Ready", "Engine not ready or game over."
            )
            return
        self.status_label.setText(f"Status: Engine ({self.engine_path}) is thinking...")
        self.is_engine_thinking_ui_flag = True
        self.update_ui_elements()
        QApplication.processEvents()
        move = self.engine_worker.request_best_move(self.board.copy(), 1.0)
        self.is_engine_thinking_ui_flag = False
        if move:
            self.handle_engine_move(move)
        else:
            self.status_label.setText("Status: Engine failed to find a move.")
        self.update_ui_elements()
        self.update_ui_from_engine_state()

    def handle_engine_move(self, move: chess.Move):
        if move and move in self.board.legal_moves:
            self.board.push(move)
            self.update_board_display()
            turn = "White" if self.board.turn == chess.WHITE else "Black"
            self.status_label.setText(
                f"Status: Engine played {move.uci()}. {turn}'s turn."
            )
            self.clock.switch()
            if self.board.is_game_over():
                self.clock.stop()
                self.handle_game_over()
            else:
                self.clock.start(self.board.turn)
        elif move:
            QMessageBox.critical(
                self, "Illegal Engine Move", f"Engine suggested: {move.uci()}"
            )
        self.update_ui_elements()

    def handle_engine_analysis(self, data: dict | None):
        if not data:
            self.analysis_display.clear()
            return
        score, pv = data.get("score"), data.get("pv")
        s = (
            f"{score.relative.score(mate_score=10000)/100.0:.2f}"
            if score and not score.is_mate()
            else f"Mate in {score.mate()}" if score else "N/A"
        )
        pv_str = " ".join(m.uci() for m in pv) if pv else ""
        self.analysis_display.setText(
            f"Score: {s} | PV: {pv_str} | Depth: {data.get('depth', '-')}"
        )

    def update_ui_from_engine_state(self):
        if not self.engine_worker:
            if hasattr(self, "status_label"):
                self.status_label.setText("Status: Engine not available.")
            return
        state = self.engine_worker.get_state()
        self.analysis_is_on_ui_flag = state == EngineState.ANALYZING

        if not self.is_in_review_mode and not self.practice_opening_mainline:
            if state == EngineState.IDLE:
                self.status_label.setText(
                    f"Status: Engine Idle. {'White' if self.board.turn == chess.WHITE else 'Black'}'s turn."
                )
            elif state == EngineState.ANALYZING:
                self.status_label.setText("Status: Engine Analyzing...")
            elif state == EngineState.THINKING:
                self.status_label.setText("Status: Engine Thinking...")
            elif state == EngineState.SHUTDOWN:
                self.status_label.setText("Status: Engine Offline.")

        if state == EngineState.ANALYZING:
            self.handle_engine_analysis(self.engine_worker.get_latest_analysis_info())
        elif state == EngineState.IDLE and not self.analysis_is_on_ui_flag:
            self.analysis_display.clear()

        self.update_ui_elements()

    def update_ui_elements(self):
        if not self.engine_worker or not self.engine_worker.engine:
            if hasattr(self, "start_analysis_button"):
                self.start_analysis_button.setEnabled(False)
            if hasattr(self, "request_move_button"):
                self.request_move_button.setEnabled(False)
            return

        state, game_over = self.engine_worker.get_state(), self.board.is_game_over()
        in_special_mode = self.is_in_review_mode or bool(self.practice_opening_mainline)

        if hasattr(self, "start_analysis_button"):
            self.start_analysis_button.setText(
                "Stop Analysis" if state == EngineState.ANALYZING else "Start Analysis"
            )
            self.start_analysis_button.setEnabled(
                not in_special_mode
                and (
                    state == EngineState.ANALYZING
                    or (
                        state == EngineState.IDLE
                        and not game_over
                        and not self.is_engine_thinking_ui_flag
                    )
                )
            )

        if hasattr(self, "request_move_button"):
            self.request_move_button.setEnabled(
                not in_special_mode
                and state == EngineState.IDLE
                and not game_over
                and not self.analysis_is_on_ui_flag
                and not self.is_engine_thinking_ui_flag
            )

    def handle_square_click(self, sq_idx: int):
        if self.is_in_review_mode:
            self.status_label.setText(
                "Status: In PGN Review. Use PGN buttons or start new game."
            )
            return
        if self.practice_opening_mainline:
            if self.selected_square is not None and self.selected_square != sq_idx:
                from_sq, to_sq = self.selected_square, sq_idx
                move = chess.Move(from_sq, to_sq)
                if move in self.board.legal_moves:
                    if self.process_practice_move(move):
                        self.selected_square = None
                        self.update_board_display()
                        return
            self.selected_square = (
                sq_idx
                if self.board.piece_at(sq_idx)
                and self.board.piece_at(sq_idx).color == self.player_color
                else None
            )
            self.update_board_display()
            return

        if self.board.is_game_over():
            self.handle_game_over()
            return
        if self.board.turn != self.player_color:
            if self.selected_square is not None:
                self.selected_square = None
                self.update_board_display()
            return
        piece = self.board.piece_at(sq_idx)
        if self.selected_square is None:
            if piece and piece.color == self.player_color:
                self.selected_square = sq_idx
                self.update_board_display()
        else:
            from_sq, to_sq = self.selected_square, sq_idx
            self.selected_square = None
            if from_sq == to_sq:
                self.update_board_display()
                return
            promo = None
            moving_piece = self.board.piece_at(from_sq)
            if (
                moving_piece
                and moving_piece.piece_type == chess.PAWN
                and chess.square_rank(to_sq) in [0, 7]
            ):
                items = ["Queen", "Rook", "Bishop", "Knight"]
                item, ok = QInputDialog.getItem(
                    self, "Promotion", "Promote to:", items, 0, False
                )
                if ok and item:
                    promo = {
                        "Queen": chess.QUEEN,
                        "Rook": chess.ROOK,
                        "Bishop": chess.BISHOP,
                        "Knight": chess.KNIGHT,
                    }[item]
                else:
                    self.selected_square = from_sq
                    self.update_board_display()
                    return
            move = chess.Move(from_sq, to_sq, promotion=promo)
            if move in self.board.legal_moves:
                self.board.push(move)
                self.update_board_display()
                self.clock.switch()
                if self.board.is_game_over():
                    self.handle_game_over()
                else:
                    self.clock.start(self.board.turn)
                    if (
                        self.board.turn != self.player_color
                        and self.engine_worker
                        and self.engine_worker.engine
                    ):
                        # AI's turn
                        QTimer.singleShot(100, self.request_engine_move_clicked)
            else:  # Illegal move
                # If the target square contains a piece of the same color (and it's player's turn), select that piece instead.
                if (
                    piece is not None
                    and piece.color == self.player_color
                    and self.board.turn == self.player_color
                ):
                    self.selected_square = to_sq  # Select the new piece
                    logger.info(
                        f"MainWindow: Illegal move, but target square has own piece. Selected {piece} at {chess.square_name(to_sq)}"
                    )
                # else self.selected_square remains None (cleared above), effectively deselecting.
                self.status_label.setText(f"Status: Illegal move: {move.uci()}")
                self.update_board_display()  # Update display to clear old selection or show new one

    def handle_game_over(self):
        if hasattr(self, "request_move_button"):
            self.request_move_button.setEnabled(False)
        self.clock.stop()
        outcome = self.board.outcome()
        msg = "Game over."
        if outcome:
            if outcome.termination == chess.Termination.CHECKMATE:
                msg = f"Checkmate! {'Black' if outcome.winner == chess.BLACK else 'White'} wins."
            elif outcome.termination == chess.Termination.STALEMATE:
                msg = "Stalemate! Draw."
            else:
                msg = f"Game over: {outcome.result()}"
        elif self.board.is_checkmate():
            msg = f"Checkmate! {'Black' if self.board.turn == chess.WHITE else 'White'} wins."
        QMessageBox.information(self, "Game Over", msg)
        if hasattr(self, "status_label"):
            self.status_label.setText(f"Status: {msg}")
        if (
            self.engine_worker
            and self.engine_worker.get_state() == EngineState.ANALYZING
        ):
            self.engine_worker.stop_analysis()
        self.end_opening_practice_mode()
        self.setup_pgn_review_mode(False)

    def handle_setup_opening_for_practice(self, opening: chess.openings.Opening):
        logger.info(f"Setting up practice for: {opening.name()}")
        self.player_color = (
            opening.board.turn
        )  # Practice from the perspective of whose turn it is in opening
        if hasattr(self.board_display, "player_color"):
            self.board_display.player_color = self.player_color

        self.end_opening_practice_mode()
        self.setup_pgn_review_mode(False)

        if (
            self.engine_worker
            and self.engine_worker.get_state() == EngineState.ANALYZING
        ):
            self.engine_worker.stop_analysis()

        self.board = (
            opening.board.copy()
        )  # Set board to the starting position of the opening
        self.practice_opening_mainline = list(opening.mainline())
        self.current_practice_move_index = -1

        self.clock.reset()
        self.clock.start(self.board.turn)
        self.selected_square = None
        self.update_board_display()
        self.status_label.setText(f"Status: Practicing: {opening.name()}")
        if hasattr(self, "prev_mainline_move_button"):
            self.prev_mainline_move_button.setVisible(True)
        if hasattr(self, "next_mainline_move_button"):
            self.next_mainline_move_button.setVisible(True)
        self.update_practice_buttons_state()
        # Disable other interactions
        self.update_ui_elements()  # This should disable analysis/engine move based on in_special_mode

    def process_practice_move(self, move: chess.Move) -> bool:
        """Validate and apply a move during opening practice.

        Returns True if the move was handled as part of practice mode.
        """
        next_idx = self.current_practice_move_index + 1
        if next_idx >= len(self.practice_opening_mainline):
            return False

        expected_move = self.practice_opening_mainline[next_idx]
        if move != expected_move:
            QMessageBox.information(
                self, "Incorrect Move", f"Expected {expected_move.uci()}"
            )
            return True

        self.board.push(move)
        self.current_practice_move_index += 1
        self.update_practice_buttons_state()

        auto_idx = self.current_practice_move_index + 1
        if (
            auto_idx < len(self.practice_opening_mainline)
            and self.board.turn != self.player_color
        ):
            auto_move = self.practice_opening_mainline[auto_idx]
            self.board.push(auto_move)
            self.current_practice_move_index += 1

        if self.current_practice_move_index >= len(self.practice_opening_mainline) - 1:
            QMessageBox.information(
                self, "Practice Complete", "You have finished this line!"
            )
            self.end_opening_practice_mode()
        return True

    def show_previous_mainline_move(self):
        if not self.practice_opening_mainline or self.current_practice_move_index < 0:
            return
        self.board.pop()
        self.current_practice_move_index -= 1
        self.update_board_display()
        self.update_practice_buttons_state()
        self.status_label.setText(
            f"Status: Practice: M {self.current_practice_move_index + 1}/{len(self.practice_opening_mainline)}"
        )

    def show_next_mainline_move(self):
        if (
            not self.practice_opening_mainline
            or self.current_practice_move_index
            >= len(self.practice_opening_mainline) - 1
        ):
            return
        self.current_practice_move_index += 1
        self.board.push(
            self.practice_opening_mainline[self.current_practice_move_index]
        )
        self.update_board_display()
        self.update_practice_buttons_state()
        self.status_label.setText(
            f"Status: Practice: M {self.current_practice_move_index + 1}/{len(self.practice_opening_mainline)}"
        )

    def update_practice_buttons_state(self):
        is_active = bool(self.practice_opening_mainline)
        if hasattr(self, "prev_mainline_move_button"):
            self.prev_mainline_move_button.setEnabled(
                is_active and self.current_practice_move_index >= 0
            )
        if hasattr(self, "next_mainline_move_button"):
            self.next_mainline_move_button.setEnabled(
                is_active
                and self.current_practice_move_index
                < len(self.practice_opening_mainline) - 1
            )

    def end_opening_practice_mode(self):
        if (
            not self.practice_opening_mainline
            and self.current_practice_move_index == -1
        ):
            return  # Not in practice mode
        self.practice_opening_mainline = []
        self.current_practice_move_index = -1
        if hasattr(self, "prev_mainline_move_button"):
            self.prev_mainline_move_button.setVisible(False)
        if hasattr(self, "next_mainline_move_button"):
            self.next_mainline_move_button.setVisible(False)
        self.update_ui_elements()  # Re-evaluate general button states

    def setup_pgn_review_mode(self, enable: bool):
        logger.info(f"Setting PGN review mode: {enable}")
        if enable:
            self.end_opening_practice_mode()
            if hasattr(self, "prev_pgn_move_button"):
                self.prev_pgn_move_button.setVisible(True)
            if hasattr(self, "next_pgn_move_button"):
                self.next_pgn_move_button.setVisible(True)
            self.update_pgn_review_buttons_state()
            self.is_in_review_mode = True
        else:
            if hasattr(self, "prev_pgn_move_button"):
                self.prev_pgn_move_button.setVisible(False)
            if hasattr(self, "next_pgn_move_button"):
                self.next_pgn_move_button.setVisible(False)
            self.is_in_review_mode = False
            self.loaded_pgn_moves = []
            self.current_loaded_pgn_move_index = -1
        self.update_ui_elements()  # Update general button states (like analysis/engine move)

    def load_game_from_pgn(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load PGN", "", "PGN (*.pgn);;All (*)"
        )
        if not path:
            return
        self.end_opening_practice_mode()
        self.setup_pgn_review_mode(False)  # Reset modes
        if (
            self.engine_worker
            and self.engine_worker.get_state() == EngineState.ANALYZING
        ):
            self.engine_worker.stop_analysis()
        try:
            with open(path, "r", encoding="utf-8") as f:
                game = chess.pgn.read_game(f)
            if game is None:
                QMessageBox.warning(self, "Load PGN Error", "Invalid PGN.")
                return

            initial_board_from_pgn = game.board()  # Board state after headers
            self.board.reset()
            self.board.set_fen(initial_board_from_pgn.fen())
            self.board.chess960 = initial_board_from_pgn.chess960
            self.board.starting_fen = (
                self.board.fen()
            )  # This is the effective starting FEN

            self.loaded_pgn_moves = list(game.mainline_moves())
            self.current_loaded_pgn_move_index = (
                -1
            )  # At the position *before* the first PGN move

            self.update_board_display()
            self.status_label.setText(
                f"PGN loaded: {os.path.basename(path)}. Board at start. Use PGN nav buttons."
            )
            self.clock.reset()
            self.clock.stop()
            self.update_clock_labels(self.clock.white_time, self.clock.black_time)
            self.selected_square = None
            self.setup_pgn_review_mode(True)
        except Exception as e:
            QMessageBox.critical(self, "Load PGN Error", f"Failed: {e}")
            self.setup_pgn_review_mode(False)

    def pgn_show_previous_move(self):
        if not self.is_in_review_mode or self.current_loaded_pgn_move_index < 0:
            return
        self.board.pop()
        self.current_loaded_pgn_move_index -= 1
        self.selected_square = None
        self.update_board_display()
        self.update_pgn_review_buttons_state()
        current_move_display = self.current_loaded_pgn_move_index + 1
        self.status_label.setText(
            f"PGN: Move {current_move_display}/{len(self.loaded_pgn_moves)}"
        )

    def pgn_show_next_move(self):
        if (
            not self.is_in_review_mode
            or self.current_loaded_pgn_move_index >= len(self.loaded_pgn_moves) - 1
        ):
            return
        self.current_loaded_pgn_move_index += 1
        move = self.loaded_pgn_moves[self.current_loaded_pgn_move_index]
        self.board.push(move)
        self.selected_square = None
        self.update_board_display()
        self.update_pgn_review_buttons_state()
        current_move_display = self.current_loaded_pgn_move_index + 1
        self.status_label.setText(
            f"PGN: Move {current_move_display}/{len(self.loaded_pgn_moves)}. Played {move.uci()}"
        )

    def update_pgn_review_buttons_state(self):
        is_active = self.is_in_review_mode and bool(self.loaded_pgn_moves)
        if hasattr(self, "prev_pgn_move_button"):
            self.prev_pgn_move_button.setEnabled(
                is_active and self.current_loaded_pgn_move_index >= 0
            )
        if hasattr(self, "next_pgn_move_button"):
            self.next_pgn_move_button.setEnabled(
                is_active
                and self.current_loaded_pgn_move_index < len(self.loaded_pgn_moves) - 1
            )

    def update_clock_labels(self, white_seconds: int, black_seconds: int):
        def fmt_time(s):
            return f"{s//60:02d}:{s%60:02d}"

        self.white_clock_label.setText(f"White: {fmt_time(white_seconds)}")
        self.black_clock_label.setText(f"Black: {fmt_time(black_seconds)}")

    def update_opening_info(self):
        try:
            opening_name = chess.polyglot.opening_name(self.board)
        except Exception:
            opening_name = "Unknown"
        self.opening_label.setText(f"Opening: {opening_name}")
        try:
            eco = chess.openings.Opening(self.board)
            self.opening_line_label.setText(f"ECO: {eco.eco()} - {eco.name()}")
        except Exception:
            self.opening_line_label.setText("ECO: -")
        moves = fetch_lichess_moves(self.board)
        if moves:
            total = sum(
                m.get("white", 0) + m.get("draws", 0) + m.get("black", 0) for m in moves
            )
            parts = [
                f"{m.get('san',m.get('uci',''))} ({100*(m.get('white',0)+m.get('draws',0)+m.get('black',0))/total:.1f}%)"
                for m in moves[:3]
                if total
            ]
            self.lichess_moves_label.setText("Lichess: " + ", ".join(parts))
        else:
            self.lichess_moves_label.setText("Lichess: n/a")

    def save_game_as_pgn(self):
        if not self.board.move_stack:
            QMessageBox.information(self, "No Moves", "No moves to save.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PGN", "game.pgn", "PGN (*.pgn);;All (*)"
        )
        if not path:
            return
        try:
            game = chess.pgn.Game()
            game.headers["Event"] = "Casual Game"
            game.headers["Site"] = "Local"
            game.headers["Date"] = datetime.datetime.now().strftime("%Y.%m.%d")
            game.headers["Round"] = "?"
            game.headers["White"] = "PlayerWhite"
            game.headers["Black"] = "PlayerBlack"
            if self.board.chess960:
                game.headers["Variant"] = "Chess960"
            if self.board.starting_fen != chess.STARTING_FEN:
                game.headers["FEN"] = self.board.starting_fen

            pgn_setup_board = chess.Board(self.board.starting_fen)
            if self.board.chess960:
                pgn_setup_board.chess960 = True
            game.setup(pgn_setup_board)

            node = game
            for move in self.board.move_stack:
                node = node.add_main_variation(move)
            game.headers["Result"] = self.board.result()
            pgn_string = game.accept(
                chess.pgn.StringExporter(headers=True, variations=True, comments=True)
            )
            with open(path, "w", encoding="utf-8") as f:
                f.write(pgn_string)
            QMessageBox.information(self, "Save Successful", f"Game saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save PGN: {e}")

    def closeEvent(self, event):
        if self.engine_worker:
            if self.engine_worker.get_state() == EngineState.ANALYZING:
                self.engine_worker.stop_analysis()
            self.engine_worker.quit_engine()
        self.ui_update_timer.stop()
        event.accept()
