from PySide6.QtCore import QObject, QTimer, Signal
import chess

class ChessClock(QObject):
    """Simple chess clock emitting remaining time each second."""

    time_changed = Signal(int, int)  # white_seconds, black_seconds

    def __init__(self, initial_seconds: int = 300):
        super().__init__()
        self.initial_seconds = initial_seconds
        self.white_seconds = initial_seconds
        self.black_seconds = initial_seconds
        self.active_color: bool | None = None  # chess.WHITE or chess.BLACK

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    def start(self, color: bool):
        """Start the clock for the given color."""
        self.active_color = color
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        """Stop the clock."""
        self._timer.stop()
        self.active_color = None

    def switch(self):
        """Switch the active side."""
        if self.active_color is not None:
            self.active_color = not self.active_color

    def reset(self, initial_seconds: int | None = None):
        if initial_seconds is not None:
            self.initial_seconds = initial_seconds
        self.white_seconds = self.initial_seconds
        self.black_seconds = self.initial_seconds
        self.active_color = None
        self._timer.stop()
        self.time_changed.emit(self.white_seconds, self.black_seconds)

    def _tick(self):
        if self.active_color is None:
            return
        if self.active_color == chess.WHITE:
            self.white_seconds = max(0, self.white_seconds - 1)
        else:
            self.black_seconds = max(0, self.black_seconds - 1)
        self.time_changed.emit(self.white_seconds, self.black_seconds)
        if self.white_seconds <= 0 or self.black_seconds <= 0:
            self.stop()
