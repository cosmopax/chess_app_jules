from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton, QTextEdit, QVBoxLayout


class ChatWindow(QDialog):
    """Simple local chat dialog."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Chat")
        self.setMinimumSize(300, 200)

        layout = QVBoxLayout(self)
        self.messages = QTextEdit()
        self.messages.setReadOnly(True)
        self.input_line = QLineEdit()
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)

        layout.addWidget(self.messages)
        layout.addWidget(self.input_line)
        layout.addWidget(self.send_button)

    def send_message(self) -> None:
        text = self.input_line.text().strip()
        if not text:
            return
        self.messages.append(f"You: {text}")
        self.input_line.clear()

