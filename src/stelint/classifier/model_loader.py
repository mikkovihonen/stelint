"""Model loading and path resolution for stelint classifier.

Handles discovery, local caching, and configuration for ONNX model weights.
"""

from __future__ import annotations

import os
from pathlib import Path

# Environment variables for model configuration
ENV_STELINT_MODEL_PATH = "STELINT_MODEL_PATH"
ENV_STELINT_VOCAB_PATH = "STELINT_VOCAB_PATH"

DEFAULT_MODEL_FILENAME = "stelint_fp_classifier.onnx"
DEFAULT_VOCAB_FILENAME = "vocab.json"


def get_cache_dir() -> Path:
    """Return the default cache directory for stelint models."""
    cache_home = os.environ.get("XDG_CACHE_HOME")
    if cache_home:
        base = Path(cache_home)
    else:
        base = Path.home() / ".cache"
    cache_dir = base / "stelint" / "models"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_model_path() -> str | None:
    """Find the path to the ONNX model file, or None if unavailable.

    Checks:
    1. STELINT_MODEL_PATH environment variable
    2. Package directory (src/stelint/models/stelint_fp_classifier.onnx)
    3. User cache directory (~/.cache/stelint/models/stelint_fp_classifier.onnx)
    """
    env_path = os.environ.get(ENV_STELINT_MODEL_PATH)
    if env_path and os.path.isfile(env_path):
        return env_path

    # Check package internal directory
    pkg_dir = Path(__file__).parent.parent / "models"
    pkg_model = pkg_dir / DEFAULT_MODEL_FILENAME
    if pkg_model.is_file():
        return str(pkg_model)

    # Check user cache directory
    cache_model = get_cache_dir() / DEFAULT_MODEL_FILENAME
    if cache_model.is_file():
        return str(cache_model)

    return None


def get_vocab_path() -> str | None:
    """Find the path to the tokenizer vocabulary file, or None if unavailable.

    Checks:
    1. STELINT_VOCAB_PATH environment variable
    2. Package directory (src/stelint/models/vocab.json)
    3. User cache directory (~/.cache/stelint/models/vocab.json)
    """
    env_path = os.environ.get(ENV_STELINT_VOCAB_PATH)
    if env_path and os.path.isfile(env_path):
        return env_path

    # Check package internal directory
    pkg_dir = Path(__file__).parent.parent / "models"
    pkg_vocab = pkg_dir / DEFAULT_VOCAB_FILENAME
    if pkg_vocab.is_file():
        return str(pkg_vocab)

    # Check user cache directory
    cache_vocab = get_cache_dir() / DEFAULT_VOCAB_FILENAME
    if cache_vocab.is_file():
        return str(cache_vocab)

    return None


def is_model_available() -> bool:
    """Check if a valid model file is available on the system."""
    return get_model_path() is not None
