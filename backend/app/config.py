"""Application configuration constants for AI Study Companion."""

import logging
import os
import secrets

logger = logging.getLogger(__name__)

DEFAULT_USER_ID = "default_user"

# --- Authentication ---
# RFC 7518 §3.2 requires >= 32 bytes of key material for HS256; a shorter
# HMAC key makes PyJWT emit an InsecureKeyLengthWarning on every decode.
_SECRET_KEY_SOURCE = os.getenv("SECRET_KEY")
if not _SECRET_KEY_SOURCE:
    generated = secrets.token_urlsafe(48)
    logger.warning(
        "SECRET_KEY is not configured; generated an ephemeral signing key. "
        "Issued login tokens will stop validating after a restart — set SECRET_KEY."
    )
    _SECRET_KEY_SOURCE = generated
elif len(_SECRET_KEY_SOURCE.encode("utf-8")) < 32:
    # Deterministic ASCII pad: same env value → same effective key, so tokens
    # stay valid across restarts. Still rotate to a real 32+ byte secret.
    _SECRET_KEY_SOURCE = (_SECRET_KEY_SOURCE + "studymate-hs256-min-length-padding")[:64]
    logger.warning(
        "SECRET_KEY is shorter than the 32-byte HS256 minimum; it was padded. "
        "Set a proper SECRET_KEY (>= 32 random bytes) in the deployment environment."
    )
SECRET_KEY = _SECRET_KEY_SOURCE
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
ALGORITHM = "HS256"

# --- Learning Loop & Concept Mastery ---
MASTERY_LAMBDA = 0.85
MASTERY_INITIAL_SCORE = 50.0
CONCEPT_MATCH_THRESHOLD = 0.88
REPEATED_MISTAKE_THRESHOLD = 3
REPEATED_MISTAKE_WINDOW = 10

# --- Confidence calibration ---
# Learners predict their own score before grading. A prediction that runs this
# far above what they actually score is the signal that matters: they believe
# they know something they cannot yet produce. Deliberately deterministic, like
# the mastery maths — the LLM never gets to judge a learner's self-awareness.
CALIBRATION_OVERCONFIDENT_GAP = 12.0
CALIBRATION_UNDERCONFIDENT_GAP = -12.0
CALIBRATION_MIN_SAMPLES = 1

# --- Grounding & Retrieval ---
MIN_RELEVANCE_THRESHOLD = 0.35
