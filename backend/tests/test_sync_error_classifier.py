"""Unit tests for the sync error classifier."""

from sqlalchemy import exc as sa_exc

from app.services.sync_error_classifier import classify_exception


class _FakeDataError(sa_exc.DataError):
    def __init__(self, message: str):
        super().__init__("orig", {}, Exception(message))

    def __str__(self):
        return self.orig.args[0] if self.orig.args else ""


def test_classify_string_data_right_truncation_returns_schema_too_long():
    exc = _FakeDataError("value too long for type character varying(500)")
    error_type, severity = classify_exception(exc)
    assert error_type == "schema_too_long"
    assert severity == "medium"


def test_classify_unicode_error_returns_encoding_error():
    exc = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
    error_type, severity = classify_exception(exc)
    assert error_type == "encoding_error"
    assert severity == "medium"


def test_classify_integrity_error_returns_db_constraint():
    exc = sa_exc.IntegrityError("orig", {}, Exception("unique violation"))
    error_type, severity = classify_exception(exc)
    assert error_type == "db_constraint"
    assert severity == "medium"


def test_classify_data_error_other_returns_db_constraint():
    """A DataError that is NOT a length truncation falls back to db_constraint."""
    exc = _FakeDataError("invalid input syntax for type uuid")
    error_type, severity = classify_exception(exc)
    assert error_type == "db_constraint"
    assert severity == "medium"


def test_classify_extraction_error_returns_extraction_failed():
    from app.services.subscription_extractor import ExtractionError

    exc = ExtractionError("AI returned malformed JSON")
    error_type, severity = classify_exception(exc)
    assert error_type == "extraction_failed"
    assert severity == "low"


def test_classify_unknown_returns_unexpected_high():
    exc = RuntimeError("something exploded")
    error_type, severity = classify_exception(exc)
    assert error_type == "unexpected"
    assert severity == "high"
