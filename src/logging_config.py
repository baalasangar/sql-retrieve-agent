"""
logging_config.py
-----------------
Central logging configuration for the SQL Retrieve Agent.

Usage (call once at application startup, before importing other modules):

    from logging_config import setup_logging
    setup_logging()

After that, every module obtains its own named logger with:

    import logging
    logger = logging.getLogger(__name__)
"""

import logging
import logging.handlers
import os

# ── Constants ────────────────────────────────────────────────────────────────

# Place the log file next to the project root (two levels above this file)
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "logs")
)
LOG_FILE = os.path.join(_PROJECT_ROOT, "agent.log")

# Log format shows time, level, module name, line number, and the message.
# This gives you exactly where in the code the log came from.
LOG_FORMAT = "[%(asctime)s] [%(levelname)-8s] [%(name)s:%(lineno)d] – %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ── Setup function ────────────────────────────────────────────────────────────

def setup_logging(
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> None:
    """
    Configure the root logger with two handlers:

    1. **StreamHandler** (console)  – shows INFO and above so the terminal is
       clean during normal operation.
    2. **RotatingFileHandler** (logs/agent.log) – captures everything from
       DEBUG upward, rotating at 1 MB with up to 3 backup files retained.

    This function is idempotent: calling it multiple times has no effect.

    Args:
        console_level: Minimum level printed to the terminal (default: INFO).
        file_level:    Minimum level written to the log file (default: DEBUG).
    """
    root_logger = logging.getLogger()

    # Guard: already configured — don't add duplicate handlers
    if root_logger.handlers:
        return

    root_logger.setLevel(logging.DEBUG)  # Let handlers filter independently

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    # ── Console handler ── INFO and above ────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # ── File handler ── DEBUG and above, with rotation ───────────────────────
    try:
        os.makedirs(_PROJECT_ROOT, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE,
            maxBytes=1 * 1024 * 1024,  # 1 MB per file
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except OSError as exc:
        # If we can't write the log file, warn on console but don't crash.
        root_logger.warning(
            "Could not create rotating file handler at '%s': %s. "
            "Logging to console only.",
            LOG_FILE,
            exc,
        )
