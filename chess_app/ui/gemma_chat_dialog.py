from __future__ import annotations

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLineEdit, QPushButton, QMessageBox
)

from chess_app.engine.engine_worker import EngineWorker, EngineState
from chess import Board
from chess_app.gemma_integration import gemma_chat


class GemmaChatDialog(QDialog):
    """Simple chat interface for Gemma 3n."""

    def __init__(self, parent=None, board: Board | None = None,
                 engine_worker: EngineWorker | None = None):
        super().__init__(parent)
        self.board = board
        self.engine_worker = engine_worker
        self.setWindowTitle("Chat with Gemma 3n")
        self.setMinimumSize(500, 400)
        layout = QVBoxLayout(self)
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field)
        send_button = QPushButton("Send")
        send_button.clicked.connect(self.send_message)
        input_layout.addWidget(send_button)
        layout.addLayout(input_layout)

    def send_message(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.chat_display.append(f"You: {text}")
        self.input_field.clear()
        moves = " ".join(m.uci() for m in self.board.move_stack) if self.board else ""
        best_move = None
        if self.engine_worker and self.engine_worker.get_state() == EngineState.IDLE:
            try:
                mv = self.engine_worker.request_best_move(self.board.copy(), 0.1)
                if mv:
                    best_move = mv.uci()
            except Exception:
                pass
        prompt = f"{text}\nMoves so far: {moves}\nEngine best move: {best_move if best_move else 'N/A'}"
        try:
            response = gemma_chat(prompt)
        except FileNotFoundError:
            QMessageBox.warning(self, "Gemma 3n", "Gemma model not configured. Set GEMMA3N_MODEL_PATH.")
            return
        except Exception as exc:
            QMessageBox.critical(self, "Gemma 3n Error", str(exc))
            return
        self.chat_display.append(f"Gemma: {response.strip()}")
