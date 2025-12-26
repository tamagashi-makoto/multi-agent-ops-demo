"""Logging utilities with PII masking support."""

import logging
import re
import sys
from typing import Any

from rich.console import Console
from rich.logging import RichHandler

from app.common.config import get_settings


class PIIMasker:
    """Mask personally identifiable information in text."""

    def __init__(self, patterns: list[str] | None = None):
        """Initialize PII masker with regex patterns.

        Args:
            patterns: List of regex patterns to mask. If None, uses settings.
        """
        if patterns is None:
            settings = get_settings()
            patterns = settings.pii_pattern_list

        self.patterns = [re.compile(p, re.IGNORECASE) for p in patterns]
        self.mask_string = "[MASKED]"

    def mask(self, text: str) -> str:
        """Mask all PII patterns in text.

        Args:
            text: Input text to mask.

        Returns:
            Text with PII masked.
        """
        result = text
        for pattern in self.patterns:
            result = pattern.sub(self.mask_string, result)
        return result

    def mask_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively mask PII in dictionary values.

        Args:
            data: Dictionary to mask.

        Returns:
            Dictionary with string values masked.
        """
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.mask(value)
            elif isinstance(value, dict):
                result[key] = self.mask_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self.mask(v) if isinstance(v, str) else v for v in value
                ]
            else:
                result[key] = value
        return result


class MaskedFormatter(logging.Formatter):
    """Logging formatter that masks PII."""

    def __init__(self, fmt: str | None = None, masker: PIIMasker | None = None):
        """Initialize masked formatter.

        Args:
            fmt: Log format string.
            masker: PII masker instance.
        """
        super().__init__(fmt)
        self.masker = masker or PIIMasker()

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with PII masking.

        Args:
            record: Log record to format.

        Returns:
            Formatted and masked log string.
        """
        # Mask the message
        if isinstance(record.msg, str):
            record.msg = self.masker.mask(record.msg)

        # Mask arguments if they are strings
        if record.args:
            if isinstance(record.args, dict):
                record.args = self.masker.mask_dict(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self.masker.mask(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )

        return super().format(record)


def get_logger(name: str, use_rich: bool = True) -> logging.Logger:
    """Get a configured logger with PII masking.

    Args:
        name: Logger name.
        use_rich: Whether to use rich console handler.

    Returns:
        Configured logger instance.
    """
    settings = get_settings()
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, settings.log_level))

    if use_rich:
        console = Console(stderr=True)
        handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            markup=True,
        )
    else:
        handler = logging.StreamHandler(sys.stderr)

    # Use masked formatter
    masker = PIIMasker()
    formatter = MaskedFormatter(
        fmt="%(name)s - %(message)s" if use_rich else "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        masker=masker,
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False

    return logger
