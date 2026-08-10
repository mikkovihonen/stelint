import os
import sys

# Ensure tests can import package modules from the `src/stelint` package root.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
