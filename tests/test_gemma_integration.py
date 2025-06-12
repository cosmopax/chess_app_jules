import importlib
import os
import sys
from unittest.mock import patch


def test_gemma_chat_builds_correct_command(tmp_path):
    env_model = str(tmp_path / "model.tflite")
    env_vocab = str(tmp_path / "vocab.model")
    os.environ['GEMMA3N_MODEL_PATH'] = env_model
    os.environ['GEMMA3N_VOCAB_PATH'] = env_vocab

    module = importlib.import_module('chess_app.gemma_integration')
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = 'ok'
        result = module.gemma_chat('hello')
        assert result == 'ok'
        expected_cmd_start = [sys.executable, module.SCRIPT_PATH]
        assert mock_run.call_args.args[0][:2] == expected_cmd_start
        assert '--model' in mock_run.call_args.args[0]
        assert env_model in mock_run.call_args.args[0]
        assert '--vocab' in mock_run.call_args.args[0]
        assert env_vocab in mock_run.call_args.args[0]

