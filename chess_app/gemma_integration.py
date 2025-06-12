import os
import subprocess
import sys

SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'run_gemma3n.py'))

def gemma_chat(prompt: str) -> str:
    """Run Gemma 3n on the given prompt and return stdout."""
    model_path = os.getenv('GEMMA3N_MODEL_PATH')
    vocab_path = os.getenv('GEMMA3N_VOCAB_PATH')
    if not model_path or not vocab_path:
        raise FileNotFoundError('Gemma model environment variables not set.')
    cmd = [sys.executable, SCRIPT_PATH, '--model', model_path, '--vocab', vocab_path, '-p', prompt]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f'Gemma invocation failed: {proc.stderr}')
    return proc.stdout
