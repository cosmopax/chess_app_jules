#!/usr/bin/env python3
import argparse
import os

import numpy as np
import sentencepiece as spm
import tensorflow as tf
from PIL import Image

# === DEFAULTS (will be overridden by CLI or env vars) ===
DEFAULT_MODEL = os.environ.get("GEMMA3N_MODEL_PATH", "path/to/model.tflite")
DEFAULT_VOCAB = os.environ.get("GEMMA3N_VOCAB_PATH", "path/to/vocab.model")
# ============================================

def load_images(shapes, image_paths):
    """Return list of [1,H,W,C] float32 arrays normalized to [0,1]."""
    arrays = []
    for path in image_paths:
        img = Image.open(path).convert("RGB")
        img = img.resize((shapes[0][2], shapes[0][1]), Image.BILINEAR)
        arr = np.asarray(img, dtype=np.float32) / 255.0
        arrays.append(np.expand_dims(arr, axis=0))
    return arrays

def load_prompts(shapes, prompts, vocab_file):
    """Return list of [1,seq_len] int32 arrays via SentencePiece."""
    sp = spm.SentencePieceProcessor(model_file=vocab_file)
    arrays = []
    for text in prompts:
        ids = sp.encode(text, out_type=int)
        seq_len = shapes[1][1]
        ids = ids[:seq_len] + [0] * (max(0, seq_len - len(ids)))
        arrays.append(np.array([ids], dtype=np.int32))
    return arrays

def main():
    parser = argparse.ArgumentParser(
        description="Run Gemma 3n TFLite inference on images and/or text"
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Path to .tflite model file")
    parser.add_argument("--vocab", default=DEFAULT_VOCAB, help="SentencePiece model file from metadata")
    parser.add_argument("--images", "-i", nargs="*", default=[], help="Paths to input images")
    parser.add_argument("--prompts", "-p", nargs="*", default=[], help="Text prompts to run")
    args = parser.parse_args()

    interpreter = tf.lite.Interpreter(model_path=args.model)
    interpreter.allocate_tensors()

    idet = interpreter.get_input_details()
    odet = interpreter.get_output_details()
    print("Input tensors:", idet)
    print("Output tensors:", odet)

    image_inputs = load_images(idet, args.images)
    prompt_inputs = load_prompts(idet, args.prompts, args.vocab)

    for inp in image_inputs:
        interpreter.set_tensor(idet[0]["index"], inp)
        interpreter.invoke()
        out = interpreter.get_tensor(odet[0]["index"])
        print(f"Image output for shape {inp.shape}:", out)

    for inp in prompt_inputs:
        interpreter.set_tensor(idet[0]["index"], inp)
        interpreter.invoke()
        out = interpreter.get_tensor(odet[0]["index"])
        print(f"Prompt output for shape {inp.shape}:", out)

if __name__ == "__main__":
    main()
