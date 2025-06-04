import sys
import os
import types
import time
from unittest.mock import patch

# Stub 'chess' module so engine_worker can be imported without real dependency
chess_stub = types.ModuleType('chess')

class DummyBoard:
    def fen(self):
        return "dummy"

    def copy(self):
        return DummyBoard()

chess_stub.Board = DummyBoard

engine_module = types.ModuleType('chess.engine')

class DummyEngine:
    def analysis(self, board):
        class _Ctx:
            def __enter__(self_inner):
                def _gen():
                    for _ in range(2):
                        time.sleep(0.01)
                        yield {}
                return _gen()

            def __exit__(self_inner, exc_type, exc, tb):
                return False

        return _Ctx()

    def quit(self):
        pass

    def play(self, board, limit):
        class _R:
            move = None
        return _R()

engine_module.SimpleEngine = types.SimpleNamespace(popen_uci=lambda path: DummyEngine())
engine_module.EngineTerminatedError = Exception
engine_module.Limit = lambda **kwargs: None

chess_stub.engine = engine_module

sys.modules.setdefault('chess', chess_stub)
sys.modules.setdefault('chess.engine', engine_module)

# Ensure project modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from chess_app.engine.engine_worker import EngineWorker, EngineState


def test_engine_worker_start_stop():
    with patch('chess.engine.SimpleEngine.popen_uci', return_value=DummyEngine()):
        worker = EngineWorker(engine_path='dummy')
        # Wait for engine initialization
        timeout = time.time() + 1.0
        while worker.engine is None and time.time() < timeout:
            time.sleep(0.01)

        board = DummyBoard()
        worker.start_analysis(board)
        time.sleep(0.1)
        worker.stop_analysis()
        assert worker.get_state() == EngineState.IDLE
        worker.quit_engine()

