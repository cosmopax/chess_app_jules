import enum
import logging
import queue
import threading
import time
import chess
import chess.engine

# This module defines the EngineWorker class which manages interactions with a UCI chess engine.
# It runs the engine in a separate thread and communicates with it via commands.
import enum
import logging
import queue
import threading
import time
import chess
import chess.engine

# Configure logging for this module. The root logger is configured in main.py.
# Standard format: %(asctime)s - %(name)s - %(levelname)s - %(message)s
logger = logging.getLogger(__name__)

class EngineState(enum.Enum):
    """Represents the various states of the EngineWorker."""
    IDLE = 1        # Engine is initialized and waiting for commands.
    ANALYZING = 2   # Engine is currently analyzing a position.
    THINKING = 3    # Engine is currently thinking to find the best move.
    SHUTDOWN = 4    # Engine is shut down or encountered a critical error.

class EngineWorker:
    """
    Manages a UCI chess engine in a separate thread.
    Handles commands for analysis, finding the best move, and engine lifecycle.
    """
    def __init__(self, engine_path: str):
        self.engine_path: str = engine_path
        self.engine: chess.engine.SimpleEngine | None = None
        self.state: EngineState = EngineState.IDLE
        self.command_queue: queue.Queue = queue.Queue()

        # stop_event: Signals the analysis loop within _handle_start_analysis to terminate.
        # It's set by _handle_stop_analysis (called by stop_analysis) or _handle_quit.
        self.stop_event: threading.Event = threading.Event()

        # analysis_stopped_event: Used by the public stop_analysis() method to block until
        # the analysis loop has fully completed its cleanup and set this event.
        # It's also used in _handle_quit to ensure analysis finishes before engine quit.
        self.analysis_stopped_event: threading.Event = threading.Event()

        # analysis_info: Stores the chess.engine.AnalysisResult object when analysis is active.
        # This object is an iterable that yields analysis information. It's stored here
        # to allow the analysis loop in _handle_start_analysis to iterate over it.
        # It is cleared when analysis stops.
        self.analysis_info: chess.engine.AnalysisResult | None = None

        # latest_analysis_info: Holds the most recent raw dictionary of analysis info
        # received from the engine. This can be polled by the UI thread.
        self.latest_analysis_info: dict | None = None

        # The worker_thread executes the `run` method, which contains the main command loop.
        self.worker_thread: threading.Thread = threading.Thread(target=self.run, name="EngineWorkerThread", daemon=True)
        self.worker_thread.start()
        logger.info(f"EngineWorker initialized for {engine_path} and worker thread started.")

    def _initialize_engine(self) -> bool:
        """
        Initializes the chess engine. This method is called by the worker thread.
        Returns True if successful, False otherwise.
        """
        if self.engine:
            logger.info("Engine _initialize_engine: Engine already initialized.")
            return True
        try:
            logger.info(f"Engine _initialize_engine: Initializing chess engine from path: {self.engine_path}")
            self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            self.analysis_stopped_event.set() # Initialize as set, as no analysis is running.
            logger.info("Engine _initialize_engine: Chess engine initialized successfully.")
            return True
        except Exception as e:
            logger.error(f"Engine _initialize_engine: Failed to initialize chess engine: {e}", exc_info=True)
            self.state = EngineState.SHUTDOWN # Critical failure, move to SHUTDOWN
            self.analysis_stopped_event.set() # Ensure any waiters (though unlikely here) are released.
            return False

    def run(self):
        """
        The main loop for the worker thread.
        Initializes the engine and then processes commands from the command_queue.
        """
        if not self._initialize_engine():
            logger.error("Engine run: Engine initialization failed. Worker thread stopping.")
            # State is already SHUTDOWN if _initialize_engine failed.
            return

        logger.info("Engine run: Command loop started.")
        while self.state != EngineState.SHUTDOWN:
            try:
                # Wait for a command with a timeout to allow periodic checks of the SHUTDOWN state.
                command, args_tuple = self.command_queue.get(timeout=1)
                args = args_tuple if isinstance(args_tuple, tuple) else (args_tuple,) # Ensure args is a tuple

                logger.info(f"Engine run: Received command: {command} with args: {args if args else ''}")

                if command == "START_ANALYSIS":
                    self._handle_start_analysis(*args)
                elif command == "STOP_ANALYSIS":
                    self._handle_stop_analysis() # No arguments expected for _handle_stop_analysis
                elif command == "FIND_BEST_MOVE":
                    self._handle_find_best_move(*args)
                elif command == "QUIT":
                    self._handle_quit()
                    # _handle_quit sets state to SHUTDOWN, which will terminate the loop.
                    break
                else:
                    logger.warning(f"Engine run: Unknown command received: {command}")

                self.command_queue.task_done() # Mark command as processed

            except queue.Empty:
                # Timeout occurred while waiting for a command. Loop continues to check SHUTDOWN state.
                continue
            except Exception as e:
                logger.error(f"Engine run: Unexpected error in command loop: {e}", exc_info=True)
                # Consider if specific errors need more graceful handling or state changes.
                # For now, most unexpected errors don't change the worker's operational state unless critical.

        self._cleanup_engine()
        logger.info("Engine run: Command loop terminated. Worker thread finishing.")

    def _handle_start_analysis(self, board: chess.Board):
        """Handles the START_ANALYSIS command."""
        if self.state != EngineState.IDLE:
            logger.warning(f"Engine _handle_start_analysis: Engine not IDLE (state: {self.state}). Cannot start analysis.")
            return

        if not self.engine: # Should not happen if initialized correctly and not shut down.
            logger.error("Engine _handle_start_analysis: Engine not initialized. Cannot start analysis.")
            return

        logger.info("Engine _handle_start_analysis: Changing state to ANALYZING.")
        self.state = EngineState.ANALYZING
        self.stop_event.clear()             # Clear the stop signal for the new analysis session.
        self.analysis_stopped_event.clear() # Clear this event; it will be set when analysis truly stops.
        self.latest_analysis_info = None    # Reset previous analysis data.
        logger.info("Engine _handle_start_analysis: Starting continuous analysis.")

        try:
            # The `with self.engine.analysis(...)` block ensures the analysis process
            # is properly managed and closed when exiting the block.
            # This is a blocking call in terms of this handler, but it iterates, yielding info.
            # Pass the worker's stop_event to the engine so analysis can
            # terminate promptly when stop_analysis() is called in tests or UI.
            with self.engine.analysis(board, stop=self.stop_event) as analysis_result:
                # self.analysis_info is stored to provide access to the AnalysisResult object,
                # primarily for iterating through the analysis information stream.
                self.analysis_info = analysis_result
                for info in self.analysis_info:
                    if self.stop_event.is_set(): # Check if a stop has been requested.
                        logger.info("Engine _handle_start_analysis: Stop event detected during analysis. Terminating analysis stream.")
                        break
                    self.latest_analysis_info = info # Store the latest piece of analysis.
                    # Detailed logging of every piece of info can be verbose; DEBUG level is appropriate.
                    score = info.get('score')
                    pv_moves = info.get('pv')
                    if score is not None and pv_moves is not None:
                        logger.debug(f"Engine _handle_start_analysis: Analysis - Score: {score}, PV: {[str(m) for m in pv_moves]}")

        except chess.engine.EngineTerminatedError:
            logger.error("Engine _handle_start_analysis: Engine terminated unexpectedly during analysis.", exc_info=True)
            self._handle_engine_failure() # Handle critical engine failure.
        except Exception as e:
            # Covers other potential errors during analysis setup or streaming.
            logger.error(f"Engine _handle_start_analysis: An error occurred during analysis: {e}", exc_info=True)
        finally:
            logger.info("Engine _handle_start_analysis: Analysis loop/block finished.")
            # Ensure `analysis_info` is cleared as the context manager (`with`) should have closed it.
            self.analysis_info = None
            self.state = EngineState.IDLE # Return to IDLE state.
            # self.stop_event is typically cleared by the requester or if it's a one-time signal.
            # Here, clearing it ensures it's reset for any future analysis start.
            self.stop_event.clear()
            self.analysis_stopped_event.set() # Signal that analysis is fully stopped and cleaned up.
            logger.info("Engine _handle_start_analysis: Engine state set to IDLE and analysis_stopped_event is set.")


    def _handle_stop_analysis(self):
        """
        Handles the STOP_ANALYSIS command. Signals the analysis loop to terminate.
        The actual state change to IDLE and setting of `analysis_stopped_event`
        occurs in the `finally` block of `_handle_start_analysis`.
        """
        if self.state != EngineState.ANALYZING:
            logger.warning(f"Engine _handle_stop_analysis: Engine not in ANALYZING state (current: {self.state}). Cannot stop analysis.")
            # If analysis is not running, ensure analysis_stopped_event is set so any callers don't hang.
            self.analysis_stopped_event.set()
            return

        logger.info("Engine _handle_stop_analysis: Processing STOP_ANALYSIS command. Setting stop_event.")
        self.stop_event.set() # Signal the analysis loop in _handle_start_analysis to terminate.
        # The public `stop_analysis()` method will wait on `self.analysis_stopped_event`.

    def _handle_find_best_move(self, board: chess.Board, time_limit: float, result_queue: queue.Queue | None = None):
        """Handles the FIND_BEST_MOVE command. This is a blocking operation for the engine."""
        if self.state != EngineState.IDLE:
            logger.warning(f"Engine _handle_find_best_move: Engine not IDLE (state: {self.state}). Cannot find best move now.")
            if result_queue:
                result_queue.put(None) # Signal error or inability to process.
            return

        if not self.engine:
            logger.error("Engine _handle_find_best_move: Engine not initialized. Cannot find best move.")
            if result_queue:
                result_queue.put(None)
            return

        logger.info(f"Engine _handle_find_best_move: Changing state to THINKING for board: {board.fen()} with time limit: {time_limit}s.")
        self.state = EngineState.THINKING
        best_move = None
        try:
            # This is a blocking call to the chess engine.
            result = self.engine.play(board, chess.engine.Limit(time=time_limit))
            best_move = result.move
            logger.info(f"Engine _handle_find_best_move: Best move found: {best_move}")
        except chess.engine.EngineTerminatedError:
            logger.error("Engine _handle_find_best_move: Engine terminated unexpectedly while finding best move.", exc_info=True)
            self._handle_engine_failure() # Handle critical engine failure.
        except Exception as e:
            logger.error(f"Engine _handle_find_best_move: Error finding best move: {e}", exc_info=True)
        finally:
            self.state = EngineState.IDLE # Return to IDLE state once finished or if an error occurred.
            logger.info("Engine _handle_find_best_move: Finished finding best move. Engine state set to IDLE.")
            if result_queue:
                result_queue.put(best_move) # Send the result (or None if error) back to the requester.

    def _handle_engine_failure(self):
        """Handles critical engine failures, like unexpected termination."""
        logger.critical("Engine _handle_engine_failure: Critical engine error detected. Attempting to handle.")
        # Log with ERROR as it's a significant problem affecting functionality. CRITICAL for the initial detection.
        logger.error("Engine _handle_engine_failure: Setting state to SHUTDOWN and attempting to close engine.")
        self.state = EngineState.SHUTDOWN

        if self.engine:
            try:
                self.engine.quit() # Attempt a graceful quit.
                logger.info("Engine _handle_engine_failure: Engine quit method called.")
            except chess.engine.EngineTerminatedError:
                logger.info("Engine _handle_engine_failure: Engine already terminated.")
            except Exception as e:
                logger.error(f"Engine _handle_engine_failure: Exception during emergency engine quit: {e}", exc_info=True)
            self.engine = None # Discard the engine instance.

        # Ensure any threads waiting on these events are unblocked.
        self.analysis_stopped_event.set()
        self.stop_event.set() # Signal any active analysis loop to stop, if it hasn't already.
        logger.info("Engine _handle_engine_failure: Engine failure handling complete.")

    def _handle_quit(self):
        """Handles the QUIT command. Prepares the worker for shutdown."""
        logger.info("Engine _handle_quit: Processing QUIT command.")

        # If currently analyzing, attempt to stop analysis gracefully first.
        if self.state == EngineState.ANALYZING:
            logger.info("Engine _handle_quit: Quit requested during analysis. Signaling analysis to stop.")
            self.stop_event.set() # Signal the analysis loop to stop.
            # Wait for the analysis loop's `finally` block to set `analysis_stopped_event`.
            # This ensures analysis resources are released before engine quit.
            if not self.analysis_stopped_event.wait(timeout=5.0): # Timeout to prevent indefinite blocking.
                 logger.warning("Engine _handle_quit: Timeout waiting for analysis to stop during quit. Proceeding with engine shutdown.")
            else:
                 logger.info("Engine _handle_quit: Analysis stopped cleanly.")

        logger.info("Engine _handle_quit: Setting state to SHUTDOWN.")
        self.state = EngineState.SHUTDOWN # Signal the main run loop to terminate.

    def _cleanup_engine(self):
        """Cleans up engine resources, primarily quitting the engine process."""
        logger.info("Engine _cleanup_engine: Cleaning up engine resources.")
        if self.engine:
            try:
                logger.info("Engine _cleanup_engine: Quitting chess engine process.")
                self.engine.quit()
                logger.info("Engine _cleanup_engine: Chess engine quit successfully.")
            except chess.engine.EngineTerminatedError: # If engine process already died
                logger.info("Engine _cleanup_engine: Engine already terminated when attempting cleanup quit.")
            except Exception as e:
                logger.error(f"Engine _cleanup_engine: Error quitting engine during cleanup: {e}", exc_info=True)
            self.engine = None

        # Ensure this event is set so any callers to public methods like stop_analysis()
        # do not hang if they were called around the time of shutdown.
        self.analysis_stopped_event.set()
        logger.info("Engine _cleanup_engine: Cleanup complete.")

    # --- Public methods to be called from other threads ---

    def start_analysis(self, board: chess.Board):
        """Public method to queue a START_ANALYSIS command."""
        if not isinstance(board, chess.Board):
            logger.error(f"Engine start_analysis: Invalid board type provided: {type(board)}")
            return
        logger.info("Engine start_analysis: Queuing START_ANALYSIS command.")
        self.command_queue.put(("START_ANALYSIS", (board,)))

    def stop_analysis(self) -> bool:
        """
        Public method to stop ongoing analysis. This method is blocking.
        It signals the worker thread to stop analysis and waits for confirmation.
        Returns True if analysis stopped cleanly within timeout, False otherwise.
        """
        logger.info("Engine stop_analysis: Requesting to stop analysis.")
        current_engine_state = self.get_state()

        if current_engine_state != EngineState.ANALYZING:
            logger.warning(f"Engine stop_analysis: Engine not in ANALYZING state (current: {current_engine_state}). Stop request ignored or analysis already stopped.")
            # If not analyzing, analysis_stopped_event should ideally already be set.
            # If it was IDLE, it's set. If it was THINKING, this call shouldn't occur.
            # If it was SHUTDOWN, it's also set.
            # self.analysis_stopped_event.set() # Avoid setting it here directly; rely on worker thread's flow.
            return True # Considered "stopped" as it wasn't running.

        # Signal the worker thread to stop analysis.
        # The worker thread's _handle_stop_analysis will set self.stop_event.
        # Then, the analysis loop in _handle_start_analysis will see this event,
        # exit, and its `finally` block will set self.analysis_stopped_event.
        self.command_queue.put(("STOP_ANALYSIS", None)) # Send command to worker

        logger.info("Engine stop_analysis: STOP_ANALYSIS command queued. Waiting for analysis_stopped_event.")

        # Wait for the analysis loop's `finally` block in the worker thread to set this event.
        # This confirms that the analysis has fully stopped and resources are cleaned up.
        # A timeout is crucial to prevent the calling thread (e.g., UI thread) from hanging indefinitely
        # if something goes wrong in the worker thread's analysis loop.
        if not self.analysis_stopped_event.wait(timeout=10.0):
            logger.error("Engine stop_analysis: Timeout waiting for analysis_stopped_event. Analysis may not have stopped cleanly in the engine process.")
            # If timeout occurs, the analysis loop in the worker thread might be stuck.
            # Forcing the state to IDLE here from an external thread is risky and might hide underlying issues.
            # The worker thread itself should manage its state.
            # However, we must set analysis_stopped_event to unblock any other potential waiters
            # and to fulfill the contract of this method if it was called again.
            # This was added in a previous step.
            self.analysis_stopped_event.set()
            return False # Indicate timeout and potential issue.
        else:
            logger.info("Engine stop_analysis: Analysis confirmed stopped (analysis_stopped_event was set). Engine should be IDLE.")
            return True # Indicate clean stop.


    def request_best_move(self, board: chess.Board, time_limit: float) -> chess.Move | None:
        """
        Public method to request the best move for a given board and time limit.
        This method is blocking as it waits for the engine's response via a queue.
        Returns the best move (chess.Move) or None if no move found or error.
        """
        # Pre-condition checks in the calling thread for immediate feedback.
        if self.get_state() != EngineState.IDLE:
            logger.warning(f"Engine request_best_move: Engine not IDLE (state: {self.get_state()}). Best move request rejected.")
            return None

        if not isinstance(board, chess.Board):
            logger.error(f"Engine request_best_move: Invalid board type: {type(board)}")
            return None
        if not isinstance(time_limit, (float, int)) or time_limit <= 0:
            logger.error(f"Engine request_best_move: Invalid time_limit: {time_limit}")
            return None

        result_queue: queue.Queue = queue.Queue() # Queue for receiving the result from the worker thread.
        self.command_queue.put(("FIND_BEST_MOVE", (board, time_limit, result_queue)))

        logger.info("Engine request_best_move: FIND_BEST_MOVE command queued. Waiting for result.")
        try:
            # Blocking wait for the result from the worker thread.
            # Timeout slightly longer than engine's thinking time for safety.
            best_move = result_queue.get(timeout=time_limit + 5.0)
            if best_move:
                logger.info(f"Engine request_best_move: Best move received from worker: {best_move}")
            else:
                logger.warning("Engine request_best_move: Received None or no move from worker.")
            return best_move
        except queue.Empty:
            logger.error(f"Engine request_best_move: Timeout waiting for best move result from worker thread (limit: {time_limit + 5.0}s).")
            return None
        except Exception as e: # Should not happen if worker thread handles its errors.
            logger.error(f"Engine request_best_move: Exception retrieving best move result: {e}", exc_info=True)
            return None


    def quit_engine(self):
        """
        Public method to shut down the engine worker and its associated engine process.
        This method is blocking and waits for the worker thread to terminate.
        """
        logger.info("Engine quit_engine: Requesting to quit engine worker.")
        if self.state != EngineState.SHUTDOWN :
            logger.info("Engine quit_engine: Queuing QUIT command.")
            self.command_queue.put(("QUIT", None))
            try:
                # Wait for the worker thread to finish its execution.
                # The run() method will exit once state is SHUTDOWN and cleanup is done.
                self.worker_thread.join(timeout=10.0)
                if self.worker_thread.is_alive():
                    logger.error("Engine quit_engine: Worker thread did not terminate cleanly after QUIT command and join timeout.")
                else:
                    logger.info("Engine quit_engine: Worker thread terminated successfully.")
            except Exception as e: # Catch potential errors during join, though rare.
                logger.error(f"Engine quit_engine: Exception during worker_thread.join: {e}", exc_info=True)
        else:
            logger.info("Engine quit_engine: Engine worker already in SHUTDOWN state.")

        # Final check, even if already shutdown, ensure thread is not alive if it exists
        if hasattr(self, 'worker_thread') and self.worker_thread.is_alive():
             logger.warning("Engine quit_engine: Worker thread is still alive after quit sequence. This might indicate an issue.")

        logger.info("Engine quit_engine: Quit sequence finished.")

    def get_state(self) -> EngineState:
        """Returns the current state of the engine worker."""
        return self.state

    def get_latest_analysis_info(self) -> dict | None:
        """Returns the most recent analysis info dictionary if available."""
        return self.latest_analysis_info

if __name__ == '__main__':
    # This example demonstrates basic usage of the EngineWorker.
    # It assumes a UCI chess engine (like Stockfish) is available.
    # Configure logging for the example.
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main_logger = logging.getLogger(__name__) # Use __name__ for the logger in this example context.

    ENGINE_PATH = "stockfish" # Replace with the actual path if not in PATH
    main_logger.info(f"Example Main: Attempting to use engine: {ENGINE_PATH}")

    worker = None
    try:
        worker = EngineWorker(engine_path=ENGINE_PATH)
    except Exception as e: # Catch potential errors during EngineWorker instantiation
        main_logger.critical(f"Example Main: Failed to instantiate EngineWorker: {e}", exc_info=True)
        sys.exit(1) # Use sys.exit for script termination

    # Allow time for engine initialization by waiting for IDLE state
    init_wait_start = time.time()
    init_timeout_seconds = 10 # Increased timeout for robust initialization
    while worker.get_state() != EngineState.IDLE and worker.get_state() != EngineState.SHUTDOWN:
        main_logger.info(f"Example Main: Waiting for engine to initialize... current state: {worker.get_state()}")
        if time.time() - init_wait_start > init_timeout_seconds:
            main_logger.error("Example Main: Timeout waiting for engine initialization.")
            if worker: worker.quit_engine()
            sys.exit(1)
        time.sleep(0.5)

    if worker.get_state() == EngineState.SHUTDOWN or not worker.engine:
        main_logger.error(f"Example Main: Engine did not initialize properly. Current state: {worker.get_state()}. Exiting.")
        if worker: worker.quit_engine() # Attempt cleanup if worker exists
        sys.exit(1)

    main_logger.info(f"Example Main: Engine initialized. Current state: {worker.get_state()}")

    # --- Test Case 1: Start and Stop Analysis ---
    if worker.get_state() == EngineState.IDLE:
        main_logger.info("--- Example Main: Test Case 1: Start and Stop Analysis ---")
        current_board = chess.Board()
        main_logger.info(f"Example Main: Requesting to start analysis on FEN: {current_board.fen()}")
        worker.start_analysis(current_board.copy())

        time.sleep(0.5) # Let worker pick up command and start analysis
        if worker.get_state() == EngineState.ANALYZING:
            main_logger.info("Example Main: Analysis started. Let it run for a few seconds...")
            time.sleep(3) # Let analysis run
            latest_info = worker.get_latest_analysis_info()
            main_logger.info(f"Example Main: Latest analysis info during run: {latest_info}")
            main_logger.info("Example Main: Requesting to stop analysis.")
            if worker.stop_analysis(): # stop_analysis is blocking
                main_logger.info(f"Example Main: Analysis stopped successfully. Engine state: {worker.get_state()}")
            else:
                main_logger.warning(f"Example Main: Analysis stop timed out. Engine state: {worker.get_state()}")
        else:
            main_logger.warning(f"Example Main: Failed to start analysis. State: {worker.get_state()}")
            if worker.get_state() != EngineState.IDLE : # If stuck in a weird state
                 worker.stop_analysis() # Attempt to clean up

    time.sleep(1) # Pause between tests

    # --- Test Case 2: Request Best Move ---
    if worker.get_state() == EngineState.IDLE:
        main_logger.info("--- Example Main: Test Case 2: Request Best Move ---")
        current_board = chess.Board()
        main_logger.info(f"Example Main: Requesting best move for FEN: {current_board.fen()} (Time limit: 1s)")
        move = worker.request_best_move(current_board.copy(), time_limit=1.0) # Blocking
        if move:
            main_logger.info(f"Example Main: Best move received: {move}")
        else:
            main_logger.warning("Example Main: Did not receive a best move.")
        main_logger.info(f"Example Main: Engine state after best move: {worker.get_state()}")
    else:
        main_logger.warning(f"Example Main: Engine not IDLE (state: {worker.get_state()}), skipping best move test.")

    time.sleep(1)

    # --- Test Case 3: Invalid request (find move while analyzing) ---
    if worker.get_state() == EngineState.IDLE:
        main_logger.info("--- Example Main: Test Case 3: Find move while analyzing (expected failure/rejection) ---")
        current_board = chess.Board()
        worker.start_analysis(current_board.copy())
        time.sleep(0.2) # Ensure analysis starts
        if worker.get_state() == EngineState.ANALYZING:
            main_logger.info("Example Main: Analysis started. Now attempting to request best move (should be rejected).")
            move = worker.request_best_move(current_board.copy(), time_limit=0.5)
            if move is None:
                main_logger.info("Example Main: Best move request was correctly rejected or failed as engine was busy.")
            else:
                main_logger.error(f"Example Main: Best move was unexpectedly processed: {move}")
            main_logger.info("Example Main: Stopping analysis for Test Case 3.")
            worker.stop_analysis()
        else:
            main_logger.warning("Example Main: Could not start analysis for Test Case 3")

    main_logger.info(f"Example Main: Final engine state before explicit quit: {worker.get_state()}")
    # --- Quit Engine ---
    main_logger.info("--- Example Main: Quitting Engine ---")
    worker.quit_engine()
    main_logger.info(f"Example Main: Engine quit requested. Final state from get_state: {worker.get_state()}")
    main_logger.info("Example Main: Example script finished.")
