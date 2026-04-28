"""Unit tests for byte-aware string truncation."""

from app.utils.string_truncate import truncate_to_bytes


def test_truncate_none_returns_none():
    assert truncate_to_bytes(None, 100) is None


def test_truncate_short_string_returns_unchanged():
    assert truncate_to_bytes("hello", 100) == "hello"


def test_truncate_long_ascii_caps_at_max_minus_marker():
    s = "a" * 200
    out = truncate_to_bytes(s, max_bytes=100, marker="[T]")
    assert out.endswith("[T]")
    assert len(out.encode("utf-8")) <= 100


def test_truncate_multibyte_does_not_split_codepoint():
    # 'é' is 2 bytes in UTF-8. 50 of them = 100 bytes.
    s = "é" * 50
    out = truncate_to_bytes(s, max_bytes=20, marker="")
    # Ensure we did not produce invalid UTF-8 (i.e. cut mid-codepoint)
    out.encode("utf-8").decode("utf-8")
    assert len(out.encode("utf-8")) <= 20


def test_truncate_marker_fits_in_max_bytes():
    s = "x" * 100
    out = truncate_to_bytes(s, max_bytes=10, marker="[truncated]")
    # marker is 11 bytes which exceeds max — implementation must fall back
    # to a smaller marker rather than overflow. Acceptable result: truncate
    # without a marker.
    assert len(out.encode("utf-8")) <= 10


def test_truncate_marker_preserved_when_truncation_happens():
    s = "x" * 200
    out = truncate_to_bytes(s, max_bytes=100, marker="...")
    assert out.endswith("...")


def test_truncate_marker_absent_when_no_truncation_needed():
    out = truncate_to_bytes("hi", max_bytes=100, marker="...")
    assert out == "hi"
