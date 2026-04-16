"""Tests for scoped_input_validator — input caps for source_urls."""

import pytest

from app.services.scoped_input_validator import (
    MAX_SOURCE_URLS,
    MAX_URL_EXTRACT_CHARS,
    ScopedInputError,
    validate_scoped_inputs,
)


def test_validate_empty_returns_empty_list():
    assert validate_scoped_inputs(None) == []
    assert validate_scoped_inputs([]) == []


def test_validate_below_cap_passes_through():
    urls = ["https://example.com", "https://foo.com"]
    assert validate_scoped_inputs(urls) == urls


def test_validate_at_cap_passes_through():
    urls = [f"https://{i}.example.com" for i in range(MAX_SOURCE_URLS)]
    assert validate_scoped_inputs(urls) == urls


def test_validate_over_cap_raises_structured_error():
    urls = [f"https://{i}.example.com" for i in range(MAX_SOURCE_URLS + 1)]
    with pytest.raises(ScopedInputError) as exc_info:
        validate_scoped_inputs(urls)

    err = exc_info.value
    assert err.payload["error_code"] == "SCOPED_INPUT_LIMIT_EXCEEDED"
    assert err.payload["field"] == "source_urls"
    assert err.payload["limit"] == MAX_SOURCE_URLS
    assert err.payload["got"] == MAX_SOURCE_URLS + 1
    # Human-readable message should include the numbers
    assert str(MAX_SOURCE_URLS) in err.payload["error"]
    assert "Too many source URLs" in err.payload["error"]


def test_max_url_extract_chars_exported():
    # Task code depends on this constant being importable and a positive int
    assert isinstance(MAX_URL_EXTRACT_CHARS, int)
    assert MAX_URL_EXTRACT_CHARS > 0
