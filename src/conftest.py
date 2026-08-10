import os
import sys

import nltk
import pytest

# Ensure tests can import package modules from the `src` package root.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def pytest_configure(config):
    """Download required nltk data before tests."""
    nltk.download("wordnet", quiet=True)
    nltk.download("punkt", quiet=True)
    nltk.download("punkt_tab", quiet=True)


@pytest.fixture
def nlp_model():
    """Load spaCy model once for all tests."""
    import spacy

    return spacy.load("en_core_web_sm")
