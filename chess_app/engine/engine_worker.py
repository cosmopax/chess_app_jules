import enum
import logging
import queue
import threading
import chess
import chess.engine

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EngineState(enum.Enum):
    IDLE = 1
    ANALYZING = 2
    THINKING = 3
    SHUTDOWN = 4 # Added a shutdown state

class EngineWorker:
    def __init__(self, engine_path):
        self.engine_path = engine_path
        self.engine = None
        self.state = EngineState.IDLE
        self.command_queue = queue.Queue()
        self.stop_event = threading.Event()  # Used to signal analysis loop to stop
        self.analysis_stopped_event = threading.Event() # Used by stop_analysis() to wait for analysis to fully stop
        self.analysis_info = None # Stores the AnalysisResult object from engine.analysis()

        self.worker_thread = threading.Thread(target=self.run, name="EngineWorkerThread", daemon=True)
        self.worker_thread.start()
        logger.info("EngineWorker initialized and worker thread started.")

    def _initialize_engine(self):
        if self.engine:
            logger.info("Engine already initialized.")
            return True
        try:
            logger.info(f"Initializing chess engine from path: {self.engine_path}")
            self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            self.analysis_stopped_event.set() # Initialize as set, because no analysis is running.
            logger.info("Chess engine initialized successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize chess engine: {e}", exc_info=True)
            self.state = EngineState.SHUTDOWN # Or some error state
            self.analysis_stopped_event.set() # Ensure any waiters are released
            return False

    def run(self):
        if not self._initialize_engine():
            logger.error("Engine initialization failed. Worker thread stopping.")
            self.state = EngineState.SHUTDOWN
            return

        logger.info("EngineWorker run loop started.")
        while self.state != EngineState.SHUTDOWN:
            try:
                command, args_tuple = self.command_queue.get(timeout=1) # Timeout to allow checking state
                args = args_tuple if isinstance(args_tuple, tuple) else (args_tuple,)

                logger.info(f"Received command: {command} with args: {args if args else ''}")

                if command == "START_ANALYSIS":
                    self._handle_start_analysis(*args)
                elif command == "STOP_ANALYSIS":
                    self._handle_stop_analysis(*args)
                elif command == "FIND_BEST_MOVE":
                    self._handle_find_best_move(*args)
                elif command == "QUIT":
                    self._handle_quit()
                    break # Exit the loop, state is set in _handle_quit
                else:
                    logger.warning(f"Unknown command: {command}")

                self.command_queue.task_done()

            except queue.Empty:
                # Timeout occurred, loop continues. Allows checking self.state for SHUTDOWN.
                continue
            except Exception as e:
                logger.error(f"Error in command loop: {e}", exc_info=True)
                # Consider more specific error handling or recovery

        self._cleanup_engine()
        logger.info("EngineWorker run loop terminated.")

    def _handle_start_analysis(self, board):
        if self.state != EngineState.IDLE:
            logger.warning(f"Engine is not IDLE (state: {self.state}). Cannot start analysis.")
            return

        if not self.engine:
            logger.error("Engine not initialized. Cannot start analysis.")
            return

        self.state = EngineState.ANALYZING
        self.stop_event.clear()
        self.analysis_stopped_event.clear() # Clear this event as analysis is starting
        logger.info("Starting analysis.")

        try:
            # This analysis runs in the worker_thread, blocking other commands until it's stopped.
            with self.engine.analysis(board) as analysis_result:
                self.analysis_info = analysis_result # Store the result object
                for info in self.analysis_info: # Iterate over the analysis stream
                    if self.stop_event.is_set():
                        logger.info("Stop event received during analysis, terminating.")
                        break
                    # Process/log analysis info (e.g., send to UI via a callback or queue)
                    score = info.get('score')
                    pv = info.get('pv')
                    if score is not None and pv is not None:
                         logger.debug(f"Analysis: Score: {score}, PV: {[str(m) for m in pv]}")
        except chess.engine.EngineTerminatedError:
            logger.error("Engine terminated unexpectedly during analysis.", exc_info=True)
            self._handle_engine_failure()
        except Exception as e:
            logger.error(f"Error during analysis: {e}", exc_info=True)
        finally:
            logger.info("Analysis loop finished.")
            if self.analysis_info:
                # The 'with' statement ensures analysis_info.close() is called.
                self.analysis_info = None
            self.state = EngineState.IDLE
            self.stop_event.clear() # Ensure event is cleared for next potential stop
            self.analysis_stopped_event.set() # Signal that analysis is fully stopped
            logger.info("Engine state set to IDLE and analysis_stopped_event is set.")


    def _handle_stop_analysis(self): # ack_event removed, using member self.analysis_stopped_event
        if self.state != EngineState.ANALYZING:
            logger.warning(f"Engine is not analyzing (state: {self.state}). Cannot stop analysis.")
            # If stop_analysis() is waiting on analysis_stopped_event, it needs to be set.
            self.analysis_stopped_event.set() # Ensure waiter is released
            return

        logger.info("Processing STOP_ANALYSIS command: Signaling analysis loop to stop.")
        self.stop_event.set()
        # The analysis loop's `finally` block will set `analysis_stopped_event`
        # and change the state to IDLE. The public `stop_analysis` method waits on this.

    def _handle_find_best_move(self, board, time_limit, result_queue=None):
        # Note: The prompt implies request_best_move checks for IDLE state before queueing.
        # This handler re-checks, which is fine.
        if self.state != EngineState.IDLE:
            logger.warning(f"Engine is not IDLE (state: {self.state}). Cannot find best move now.")
            if result_queue:
                result_queue.put(None) # Signal error or inability
            return

        if not self.engine:
            logger.error("Engine not initialized. Cannot find best move.")
            if result_queue:
                result_queue.put(None)
            return

        self.state = EngineState.THINKING
        logger.info(f"Finding best move for board: {board.fen()} with time limit: {time_limit}s")
        best_move = None
        try:
            result = self.engine.play(board, chess.engine.Limit(time=time_limit))
            best_move = result.move
            logger.info(f"Best move found: {best_move}")
        except chess.engine.EngineTerminatedError:
            logger.error("Engine terminated unexpectedly while finding best move.", exc_info=True)
            self._handle_engine_failure()
        except Exception as e:
            logger.error(f"Error finding best move: {e}", exc_info=True)
        finally:
            self.state = EngineState.IDLE
            logger.info("Finished finding best move, engine returned to IDLE state.")
            if result_queue:
                result_queue.put(best_move)

    def _handle_engine_failure(self):
        logger.error("Handling engine failure: setting state to SHUTDOWN and closing engine.")
        self.state = EngineState.SHUTDOWN # Or an ERROR state
        if self.engine:
            try:
                self.engine.quit()
            except chess.engine.EngineTerminatedError:
                logger.info("Engine already terminated.")
            except Exception as e:
                logger.error(f"Exception during emergency engine quit: {e}", exc_info=True)
            self.engine = None
        self.analysis_stopped_event.set() # Ensure any waiters are released
        self.stop_event.set() # Stop any ongoing analysis loops

    def _handle_quit(self):
        logger.info("Processing QUIT command.")
        if self.state == EngineState.ANALYZING:
            logger.info("Quit requested during analysis. Stopping analysis first.")
            self.stop_event.set()
            # The analysis loop needs to terminate and set analysis_stopped_event.
            # We should wait for it here before proceeding to quit the engine.
            if not self.analysis_stopped_event.wait(timeout=5.0): # Wait for analysis to stop
                 logger.warning("Timeout waiting for analysis to stop during quit. Proceeding with quit.")

        self.state = EngineState.SHUTDOWN # Signal run loop to terminate

    def _cleanup_engine(self):
        logger.info("Cleaning up engine resources.")
        if self.engine:
            try:
                self.engine.quit()
                logger.info("Chess engine quit successfully.")
            except chess.engine.EngineTerminatedError:
                logger.info("Engine already terminated when cleaning up.")
            except Exception as e:
                logger.error(f"Error quitting engine during cleanup: {e}", exc_info=True)
            self.engine = None
        self.analysis_stopped_event.set() # Ensure any final waiters are released

    # --- Public methods to be called from other threads ---

    def start_analysis(self, board: chess.Board):
        if not isinstance(board, chess.Board):
            logger.error("Invalid board type for start_analysis.")
            return
        logger.info("Queuing START_ANALYSIS command.")
        self.command_queue.put(("START_ANALYSIS", (board,)))

    def stop_analysis(self):
        logger.info("Requesting to stop analysis.")
        current_engine_state = self.get_state()

        if current_engine_state != EngineState.ANALYZING:
            logger.warning(f"Engine is not in ANALYZING state (current: {current_engine_state}). Stop request ignored or analysis already stopped.")
            # Ensure event is set if we are not analyzing, so no one hangs.
            # self.analysis_stopped_event.set() # This might be problematic if a start is queued right after.
            # Better to rely on the analysis loop itself to set this.
            # If it's IDLE, analysis_stopped_event should already be set from init or last stop.
            return

        # It's important that analysis_stopped_event is clear if analysis is running or about to run.
        # This call assumes that if state is ANALYZING, analysis_stopped_event is currently clear.
        # _handle_start_analysis is responsible for clearing it.

        self.command_queue.put(("STOP_ANALYSIS", ()))
        logger.info("STOP_ANALYSIS command queued. Waiting for analysis to confirm stoppage.")

        # Wait for the analysis loop's finally block to set this event
        if not self.analysis_stopped_event.wait(timeout=10.0): # Timeout for safety
            logger.error("Timeout waiting for analysis to stop. Analysis might still be running or stuck.")
        else:
            logger.info("Analysis confirmed stopped. Engine should be IDLE.")


    def request_best_move(self, board: chess.Board, time_limit: float):
        # As per prompt: "Ensure find_best_move can only be called when the engine is IDLE."
        # This implies the caller should check, or this method enforces it *before* queueing.
        if self.get_state() != EngineState.IDLE:
            logger.warning(f"Engine is not IDLE (state: {self.get_state()}). Best move request rejected.")
            return None # Or raise an exception

        if not isinstance(board, chess.Board):
            logger.error("Invalid board type for request_best_move.")
            return None
        if not isinstance(time_limit, (float, int)) or time_limit <= 0:
            logger.error("Invalid time_limit for request_best_move.")
            return None

        # For simplicity in this iteration, this will be a blocking call.
        # A more advanced version would use futures or callbacks.
        result_queue = queue.Queue()
        self.command_queue.put(("FIND_BEST_MOVE", (board, time_limit, result_queue)))

        logger.info("FIND_BEST_MOVE command queued. Waiting for result.")
        try:
            # Blocking wait for the result from the worker thread
            best_move = result_queue.get(timeout=time_limit + 5.0) # Timeout slightly longer than engine's
            logger.info(f"Best move received: {best_move}")
            return best_move
        except queue.Empty:
            logger.error("Timeout waiting for best move result from worker thread.")
            return None
        except Exception as e:
            logger.error(f"Error retrieving best move result: {e}", exc_info=True)
            return None


    def quit_engine(self):
        logger.info("Requesting to quit engine worker.")
        if self.state != EngineState.SHUTDOWN :
            self.command_queue.put(("QUIT", ()))
            self.worker_thread.join(timeout=10.0) # Wait for the run loop to terminate
            if self.worker_thread.is_alive():
                logger.error("Worker thread did not terminate cleanly.")
        else:
            logger.info("Engine already shut down.")
        logger.info("EngineWorker quit sequence finished.")

    def get_state(self):
        return self.state

if __name__ == '__main__':
    # This example assumes you have a UCI chess engine (like Stockfish)
    # available in your system PATH or provide a direct path to it.
    # On Linux, you might install it via: sudo apt-get install stockfish
    # On Windows, download the executable and provide its path.

    ENGINE_PATH = "stockfish" # Replace with the actual path if not in PATH
    # Example: ENGINE_PATH = "/usr/games/stockfish" or "C:/path/to/stockfish.exe"

    logger.info(f"Attempting to use engine: {ENGINE_PATH}")

    try:
        worker = EngineWorker(engine_path=ENGINE_PATH)
    except Exception as e:
        logger.critical(f"Failed to instantiate EngineWorker: {e}", exc_info=True)
        exit(1)

    # Allow time for engine initialization
    init_timeout = 5 # seconds
    while worker.get_state() == EngineState.IDLE and not worker.engine and init_timeout > 0 :
        logger.info(f"Waiting for engine to initialize... current state: {worker.get_state()}")
        threading.sleep(0.5)
        init_timeout -=0.5

    if not worker.engine:
        logger.error(f"Engine did not initialize after waiting. Current state: {worker.get_state()}. Exiting example.")
        worker.quit_engine()
        exit(1)

    logger.info(f"Engine initialized. Current state: {worker.get_state()}")

    # --- Test Case 1: Start and Stop Analysis ---
    if worker.get_state() == EngineState.IDLE:
        logger.info("--- Test Case 1: Start and Stop Analysis ---")
        current_board = chess.Board()
        logger.info(f"Requesting to start analysis on FEN: {current_board.fen()}")
        worker.start_analysis(current_board.copy())

        threading.sleep(0.5) # Let worker pick up command
        if worker.get_state() == EngineState.ANALYZING:
            logger.info("Analysis started. Let it run for a few seconds...")
            threading.sleep(3)
            logger.info("Requesting to stop analysis.")
            worker.stop_analysis() # This is a blocking call
            logger.info(f"Analysis stopped. Engine state: {worker.get_state()}")
        else:
            logger.warning(f"Failed to start analysis. State: {worker.get_state()}")
            worker.stop_analysis() # Attempt to clean up if stuck

    threading.sleep(1) # Pause between tests

    # --- Test Case 2: Request Best Move ---
    if worker.get_state() == EngineState.IDLE:
        logger.info("--- Test Case 2: Request Best Move ---")
        current_board = chess.Board()
        logger.info(f"Requesting best move for FEN: {current_board.fen()} (Time limit: 1s)")
        move = worker.request_best_move(current_board.copy(), time_limit=1.0) # Blocking
        if move:
            logger.info(f"Best move received: {move}")
        else:
            logger.warning("Did not receive a best move.")
        logger.info(f"Engine state after best move: {worker.get_state()}")
    else:
        logger.warning(f"Engine not IDLE (state: {worker.get_state()}), skipping best move test.")

    threading.sleep(1)

    # --- Test Case 3: Invalid request (find move while analyzing) ---
    if worker.get_state() == EngineState.IDLE:
        logger.info("--- Test Case 3: Find move while analyzing (expected failure/rejection) ---")
        current_board = chess.Board()
        worker.start_analysis(current_board.copy())
        threading.sleep(0.1) # ensure analysis starts
        if worker.get_state() == EngineState.ANALYZING:
            logger.info("Analysis started. Now attempting to request best move (should be rejected).")
            move = worker.request_best_move(current_board.copy(), time_limit=0.5)
            if move is None:
                logger.info("Best move request was correctly rejected or failed as engine was busy.")
            else:
                logger.error(f"Best move was unexpectedly processed: {move}")
            logger.info("Stopping analysis for Test Case 3.")
            worker.stop_analysis()
        else:
            logger.warning("Could not start analysis for Test Case 3")

    logger.info(f"Final engine state before explicit quit: {worker.get_state()}")
    # --- Quit Engine ---
    logger.info("--- Quitting Engine ---")
    worker.quit_engine()
    logger.info(f"Engine quit requested. Final state from get_state: {worker.get_state()}")
    logger.info("Example script finished.")
