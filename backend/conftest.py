"""
conftest.py
===========
Root pytest configuration for the StudyMate backend.

Adds the `backend/` directory to sys.path so that `from app.db.crud import ...`
works in tests without requiring an editable install.
"""
import sys
import os

# Ensure `backend/` is on the path so `app.*` imports resolve correctly.
sys.path.insert(0, os.path.dirname(__file__))
