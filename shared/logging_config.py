"""Global logging configuration, shared by every entry point (API, bot, scripts).

Every module should log via `logging.getLogger(__name__)` as usual; calling
`configure_logging()` once at process startup attaches the handler/format to
the root logger so all of those module loggers propagate into it.
"""

import logging
import os

_CONFIGURED = False


def configure_logging() -> None:
    """Configure the root logger. Safe to call more than once (no-ops after the first)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    _CONFIGURED = True
