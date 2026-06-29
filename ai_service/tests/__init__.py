"""Pytest test package for the AI Service."""

import os
import sys

# Make the project root importable when running `pytest` from ai_service/.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)