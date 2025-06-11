import socket
from typing import Tuple


class GameServer:
    """Minimal TCP server for network play."""

    def __init__(self, host: str = "0.0.0.0", port: int = 5000) -> None:
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self) -> socket.socket:
        self.sock.bind((self.host, self.port))
        self.sock.listen(1)
        conn, _addr = self.sock.accept()
        return conn


class GameClient:
    """Minimal TCP client for network play."""

    def __init__(self, host: str, port: int = 5000) -> None:
        self.sock = socket.create_connection((host, port))


def send_move(sock: socket.socket, move: str) -> None:
    sock.sendall(move.encode("utf-8") + b"\n")


def receive_move(sock: socket.socket) -> str:
    data = b""
    while not data.endswith(b"\n"):
        chunk = sock.recv(1024)
        if not chunk:
            break
        data += chunk
    return data.decode("utf-8").strip()

