"""
Logging configuration.

Standard log format used across the package; loaded once at import time
or by callers via :func:`configure_logging`. Modules should obtain a
logger via ``logging.getLogger(__name__)`` rather than calling ``print``.
"""

from __future__ import annotations

import logging

DEFAULT_FORMAT = "%(asctime)s %(levelname)-7s %(name)s :: %(message)s"
DEFAULT_DATEFMT = "%Y-%m-%dT%H:%M:%S%z"


def configure_logging(level: int = logging.INFO, fmt: str | None = None) -> None:
    """
    Configure root logging for the ``actuarial_model`` package.

    Args:
        level: Logging level (e.g. ``logging.INFO``).
        fmt: Optional custom format string; defaults to :data:`DEFAULT_FORMAT`.
    """
    logging.basicConfig(
        level=level,
        format=fmt or DEFAULT_FORMAT,
        datefmt=DEFAULT_DATEFMT,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a package-scoped logger for ``name``."""
    return logging.getLogger(name)
