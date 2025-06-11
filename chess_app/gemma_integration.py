import os
import subprocess
import sys

SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'run_gemma3n.py'))

MODEL_PATH = os.environ.get('GEMMA3N_MODEL_PATH')
VOCAB_PATH = os.environ.get('GEMMA3N_VOCAB_PATH')

def gemma_chat(prompt: str) -> str:
    """Run Gemma 3n on the given prompt and return stdout."""
    if not MODEL_PATH or not VOCAB_PATH:
        raise FileNotFoundError('Gemma model environment variables not set.')
    cmd = [sys.executable, SCRIPT_PATH, '--model', MODEL_PATH, '--vocab', VOCAB_PATH, '-p', prompt]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f'Gemma invocation failed: {proc.stderr}')
    return proc.stdout
