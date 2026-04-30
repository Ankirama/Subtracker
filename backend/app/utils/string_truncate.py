"""Byte-aware string truncation utility.

Used to defensively cap fields like ``email_messages.subject`` and
``email_messages.sender_name`` before INSERT, even though the columns are
now ``TEXT``. Defends against pathologically large provider payloads.
"""

from typing import Optional


def truncate_to_bytes(
    value: Optional[str],
    max_bytes: int,
    marker: str = "[truncated]",
) -> Optional[str]:
    """Truncate ``value`` so its UTF-8 encoding is at most ``max_bytes``.

    When truncation occurs, ``marker`` is appended (and counts toward the
    byte budget). If ``marker`` does not fit, it is dropped silently.
    Multi-byte characters are never split — the result is always valid
    UTF-8.

    ``None`` passes through unchanged.
    """
    if value is None:
        return None

    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value

    marker_bytes = marker.encode("utf-8")
    if len(marker_bytes) >= max_bytes:
        budget = max_bytes
        suffix = ""
    else:
        budget = max_bytes - len(marker_bytes)
        suffix = marker

    # Trim then re-decode with errors='ignore' to drop any partial codepoint
    truncated = encoded[:budget].decode("utf-8", errors="ignore")
    return truncated + suffix
