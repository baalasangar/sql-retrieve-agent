import sys
import os
import logging

# Ensure the src directory is on path so imports work cleanly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# ── Logging must be configured FIRST, before any project imports ──────────────
from logging_config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

# ── Now safe to import project modules ────────────────────────────────────────
from dotenv import load_dotenv

load_dotenv()
logger.debug(".env file loaded (GOOGLE_API_KEY present: %s)", bool(os.environ.get("GOOGLE_API_KEY")))

from agent.core import chat_loop

if __name__ == "__main__":
    logger.info("SQL Retrieve Agent starting up.")
    try:
        chat_loop()
    except KeyboardInterrupt:
        # Ctrl-C at the OS level (outside the inner loop) — exit cleanly
        logger.info("Process interrupted by user (KeyboardInterrupt). Exiting.")
    except SystemExit as exc:
        logger.info("SystemExit raised with code %s.", exc.code)
        raise
    except Exception:
        # Unexpected top-level crash — log with full traceback then exit
        logger.exception("Unhandled exception at top level. The agent has crashed.")
        sys.exit(1)
    finally:
        logger.info("SQL Retrieve Agent shut down.")
