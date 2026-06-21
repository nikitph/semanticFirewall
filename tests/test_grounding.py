from __future__ import annotations

import pytest

from app.exceptions import Gate3GroundingException
from app.grounding import ground_quotes


def test_valid_continuous_quote_with_normalization():
    raw = "Net\n revenue   was $4M."
    spans = ground_quotes(["net revenue was $4m"], raw)

    assert len(spans) == 1
    assert spans[0].quote == "Net\n revenue   was $4M"
    for span in spans:
        assert raw[span.start_index : span.end_index] == span.quote


def test_hallucinated_quote_fails():
    with pytest.raises(Gate3GroundingException):
        ground_quotes(["Revenue was $4M."], "Revenue was $3M.")


def test_ellipsis_monotonic_pass():
    raw = "The company reported net revenue of $4M in FY2024."
    spans = ground_quotes(["company reported...FY2024"], raw)

    assert [span.quote for span in spans] == ["company reported", "FY2024"]


def test_ellipsis_order_fail():
    raw = "FY2024 results came after the company reported revenue."
    with pytest.raises(Gate3GroundingException):
        ground_quotes(["company reported...FY2024"], raw)


def test_exact_raw_span_invariant_for_multiple_quotes():
    raw = "Alpha beta gamma. Alpha delta."
    spans = ground_quotes(["alpha...delta"], raw)

    for span in spans:
        assert raw[span.start_index : span.end_index] == span.quote
