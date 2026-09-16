"""Application configuration constants for AI Study Companion."""

import os

DEFAULT_USER_ID = "default_user"

# --- Authentication ---
SECRET_KEY = os.getenv("SECRET_KEY", "ai-study-companion-secret-key-change-in-prod-2026")
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
ALGORITHM = "HS256"

# --- Learning Loop & Concept Mastery ---
MASTERY_LAMBDA = 0.85
MASTERY_INITIAL_SCORE = 50.0
CONCEPT_MATCH_THRESHOLD = 0.88
REPEATED_MISTAKE_THRESHOLD = 3
REPEATED_MISTAKE_WINDOW = 10

# --- Grounding & Retrieval ---
MIN_RELEVANCE_THRESHOLD = 0.35
