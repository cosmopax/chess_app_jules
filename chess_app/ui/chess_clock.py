# This module defines the ChessClock class, responsible for managing game time.
import chess  # Used for chess.WHITE and chess.BLACK constants
from PySide6.QtCore import QObject, QTimer, Signal


class ChessClock(QObject):
    """
    A simple chess clock that manages time for two players (White and Black).
    It emits a `time_changed` signal every second when active, providing the
    remaining seconds for both players.
    """

    time_changed = Signal(int, int)  # Emits (white_seconds, black_seconds)

    def __init__(self, initial_seconds: int = 300):
        """
        Initializes the chess clock.
        Args:
            initial_seconds: The starting time in seconds for each player (default is 5 minutes).
        """
        super().__init__()
        self.initial_seconds: int = initial_seconds
        self.white_seconds: int = initial_seconds
        self.black_seconds: int = initial_seconds
        self.active_color: bool | None = (
            None  # Stores whose clock is currently running (chess.WHITE or chess.BLACK)
        )

        self._timer: QTimer = QTimer(self)
        self._timer.setInterval(1000)  # Timer ticks every 1000 milliseconds (1 second)
        self._timer.timeout.connect(
            self._tick
        )  # Connect timeout signal to the _tick method

    def start(self, color: bool):
        """
        Starts or resumes the clock for the specified player's turn.
        Args:
            color: The player whose clock should start (chess.WHITE or chess.BLACK).
        """
        self.active_color = color
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        """Stops or pauses the clock. No player's time will decrease."""
        self._timer.stop()
        self.active_color = None  # No color is active when stopped

    def switch(self):
        """
        Switches the active player. If White's clock was running, Black's will start, and vice versa.
        If the clock was stopped, this method does not start it but will switch who is next if started.
        """
        if self.active_color is not None:
            self.active_color = (
                not self.active_color
            )  # Toggle between chess.WHITE (True) and chess.BLACK (False)

    def reset(self, initial_seconds: int | None = None):
        """
        Resets the clock to the initial time for both players and stops the timer.
        Args:
            initial_seconds: Optionally, set a new initial time for the reset.
                             If None, uses the existing initial_seconds value.
        """
        if initial_seconds is not None:
            self.initial_seconds = initial_seconds
        self.white_seconds = self.initial_seconds
        self.black_seconds = self.initial_seconds
        self.active_color = None  # No active player after reset
        self._timer.stop()  # Ensure timer is stopped
        # Emit current times immediately after reset so UI can update.
        self.time_changed.emit(self.white_seconds, self.black_seconds)

    def _tick(self):
        """
        Internal method called by the QTimer every second.
        Decrements the active player's time and emits the `time_changed` signal.
        Stops the clock if a player's time runs out.
        """
        if (
            self.active_color is None
        ):  # Should not happen if timer is active, but as a safeguard
            return

        if self.active_color == chess.WHITE:
            self.white_seconds = max(0, self.white_seconds - 1)  # Prevent negative time
        else:  # active_color == chess.BLACK
            self.black_seconds = max(0, self.black_seconds - 1)

        self.time_changed.emit(
            self.white_seconds, self.black_seconds
        )  # Notify listeners of the time update

        # Stop the clock if either player runs out of time
        if self.white_seconds <= 0 or self.black_seconds <= 0:
            self.stop()
