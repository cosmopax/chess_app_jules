import sys
import os
import types
import time
import unittest
from unittest.mock import patch, MagicMock, PropertyMock

# --- Chess Module Stub ---
chess_stub = types.ModuleType('chess')

class DummyBoard:
    def fen(self):
        return "dummy_fen"
    def copy(self):
        return self
    def is_game_over(self):
        return False
    # Add any other methods your EngineWorker or tests might call on a board
chess_stub.Board = DummyBoard

class DummyMove:
    def __init__(self, uci_string="g1f3"): # Default to a valid UCI string
        self.uci_string = uci_string
    def uci(self):
        return self.uci_string
    def __str__(self):
        return self.uci_string
    def __bool__(self): # So `if move:` works
        return True

chess_stub.Move = DummyMove
chess_stub.Move.from_uci = lambda uci_str: DummyMove(uci_string=uci_str)

# --- Chess Engine Module Stub ---
engine_module = types.ModuleType('chess.engine')

class DummyAnalysisContext:
    def __init__(self, worker_stop_event):
        self.worker_stop_event = worker_stop_event

    def __enter__(self):
        # Yield dummy analysis info for a short period
        # In a real test, you might want more control over what's yielded
        def analysis_generator():
            count = 0
            while not self.worker_stop_event.is_set() and count < 5: # Limit iterations
                yield {"score": chess_stub.engine.PovScore(chess_stub.engine.Cp(10), chess_stub.WHITE), "pv": [chess_stub.Move.from_uci("e2e4")]}
                time.sleep(0.01) # Simulate work
                count +=1
        return analysis_generator()

    def __exit__(self, exc_type, exc_val, exc_tb):
        # print("DummyAnalysisContext exited")
        pass # Cleanup, if any

class DummyEngine:
    def __init__(self, path="dummy_engine_path"):
        self.path = path
        self.pid = 1234 # Mock PID
        self.is_alive_mock = MagicMock(return_value=True) # To mock internal engine process checks
        self.analysis_context = None
        # Expose quit as a MagicMock so tests can assert calls
        self.quit = MagicMock(side_effect=self._quit)

    def _quit(self):
        # Mark engine as no longer alive
        self.is_alive_mock.return_value = False

    def analysis(self, board, multipv=1, *, limit=None, info=None, stop=None):
        # stop event is passed from EngineWorker's self.stop_event
        # print(f"DummyEngine.analysis called with stop event: {stop}")
        self.analysis_context = DummyAnalysisContext(stop)
        return self.analysis_context

    def play(self, board, limit):
        # print(f"DummyEngine.play called for board {board.fen()} with limit {limit}")
        result = MagicMock()
        result.move = chess_stub.Move.from_uci("e2e4") # Default mock move
        return result

    def close(self):  # SimpleEngine has close, which calls quit
        self.quit()

    @property
    def is_alive(self): # Property to make it callable like engine.is_alive()
        return self.is_alive_mock()


# Mocking SimpleEngine.popen_uci to return our DummyEngine
engine_module.SimpleEngine = MagicMock()
# This global mock will be overridden by @patch in tests for specific behaviors
engine_module.SimpleEngine.popen_uci = MagicMock(return_value=DummyEngine("global_dummy"))

# Mocking specific engine states/types if needed by EngineWorker
engine_module.Cp = lambda val: val # chess.engine.Cp(10)
engine_module.Mate = lambda val: val # chess.engine.Mate(1)
engine_module.PovScore = lambda score_type, turn: {"score_type": score_type, "turn": turn} # Simplified
chess_stub.WHITE = True
chess_stub.BLACK = False

engine_module.EngineTerminatedError = type('EngineTerminatedError', (Exception,), {})
engine_module.Limit = lambda time=None, depth=None, nodes=None: {"time":time, "depth":depth, "nodes":nodes}


chess_stub.engine = engine_module
sys.modules['chess'] = chess_stub
sys.modules['chess.engine'] = engine_module


# Ensure project modules can be imported
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from chess_app.engine.engine_worker import EngineWorker, EngineState


class TestEngineWorker(unittest.TestCase):

    def setUp(self):
        # Ensure each test starts with a fresh global popen_uci mock if not using @patch for it
        # However, using @patch per test is cleaner for defining behavior.
        engine_module.SimpleEngine.popen_uci = MagicMock(return_value=DummyEngine(f"dummy_for_{self.id()}"))

    def tearDown(self):
        # Clean up any resources if necessary
        # Workers should be quit within each test.
        pass

    def wait_for_condition(self, condition_callable, timeout=3.0, interval=0.01, description="condition"):
        start_time = time.time()
        while not condition_callable():
            if time.time() - start_time > timeout:
                self.fail(f"Timeout waiting for {description}")
            time.sleep(interval)

    def wait_for_engine_state(self, worker, expected_state, timeout=2.0):
        self.wait_for_condition(lambda: worker.get_state() == expected_state,
                                timeout=timeout, description=f"engine state to be {expected_state}")

    def wait_for_engine_init(self, worker, timeout=2.0):
        self.wait_for_condition(lambda: worker.engine is not None and worker.get_state() == EngineState.IDLE,
                                timeout=timeout, description="engine to initialize and be IDLE")


    @patch('chess.engine.SimpleEngine.popen_uci')
    def test_engine_initialization_and_quit(self, mock_popen_uci):
        mock_engine_instance = DummyEngine("test_init_quit_dummy")
        mock_popen_uci.return_value = mock_engine_instance

        worker = EngineWorker(engine_path='dummy_path')
        self.wait_for_engine_init(worker)
        self.assertIsNotNone(worker.engine, "Engine should be initialized.")
        self.assertEqual(worker.get_state(), EngineState.IDLE, "Engine should be IDLE after init.")

        worker.quit_engine()
        self.wait_for_engine_state(worker, EngineState.SHUTDOWN)
        self.assertFalse(worker.worker_thread.is_alive(), "Worker thread should not be alive after quit.")
        mock_engine_instance.quit.assert_called_once()


    @patch('chess.engine.SimpleEngine.popen_uci')
    def test_engine_worker_start_stop_analysis(self, mock_popen_uci):
        mock_engine_instance = DummyEngine("test_analysis_dummy")
        mock_popen_uci.return_value = mock_engine_instance

        worker = EngineWorker(engine_path='dummy_path')
        self.wait_for_engine_init(worker)

        board = DummyBoard()
        worker.start_analysis(board)
        self.wait_for_engine_state(worker, EngineState.ANALYZING, timeout=0.5) # Analysis starts quickly

        # Let analysis run for a bit
        time.sleep(0.1) # Allow some analysis cycles

        # Ensure stop_event is clear before stopping
        self.assertFalse(worker.stop_event.is_set(), "Stop event should be clear before stop_analysis")

        worker.stop_analysis() # This is blocking

        # stop_analysis should set the stop_event, and the analysis loop's finally block
        # should set analysis_stopped_event and change state to IDLE.
        self.wait_for_engine_state(worker, EngineState.IDLE)
        self.assertTrue(worker.analysis_stopped_event.is_set(), "analysis_stopped_event should be set after analysis stops.")

        worker.quit_engine()
        self.wait_for_engine_state(worker, EngineState.SHUTDOWN)

    @patch('chess.engine.SimpleEngine.popen_uci', side_effect=Exception("Simulated engine start failure"))
    def test_engine_initialization_failure(self, mock_popen_uci_failure):
        worker = EngineWorker(engine_path='faulty_path')

        self.wait_for_engine_state(worker, EngineState.SHUTDOWN, timeout=2.0)

        self.assertIsNone(worker.engine, "Engine should be None after initialization failure.")
        self.assertEqual(worker.get_state(), EngineState.SHUTDOWN, "Engine state should be SHUTDOWN.")

        # Try quitting to ensure it handles this gracefully
        worker.quit_engine()
        # Worker thread might not have even started or exited quickly.
        # If it did start, it should not be alive.
        if hasattr(worker, 'worker_thread') and worker.worker_thread is not None:
             self.assertFalse(worker.worker_thread.is_alive(), "Worker thread should not be alive.")
        mock_popen_uci_failure.assert_called_once_with('faulty_path')

    @patch('chess.engine.SimpleEngine.popen_uci')
    def test_request_best_move(self, mock_popen_uci_success):
        mock_engine_instance = DummyEngine("test_best_move_dummy")
        # Configure the play method of this specific instance if needed
        expected_move_uci = "a1a2"
        mock_engine_instance.play = MagicMock(return_value=MagicMock(move=chess_stub.Move.from_uci(expected_move_uci)))
        mock_popen_uci_success.return_value = mock_engine_instance

        worker = EngineWorker(engine_path='dummy_path')
        self.wait_for_engine_init(worker)

        board = DummyBoard()
        returned_move = worker.request_best_move(board, time_limit=0.01) # Short time limit for test

        self.assertIsNotNone(returned_move, "Engine should return a move.")
        self.assertEqual(returned_move.uci(), expected_move_uci, f"Returned move UCI should be {expected_move_uci}.")

        # request_best_move is blocking and should return the state to IDLE itself.
        self.assertEqual(worker.get_state(), EngineState.IDLE, "Engine should return to IDLE after finding move.")
        mock_engine_instance.play.assert_called_once()

        worker.quit_engine()
        self.wait_for_engine_state(worker, EngineState.SHUTDOWN)

if __name__ == '__main__':
    unittest.main()

