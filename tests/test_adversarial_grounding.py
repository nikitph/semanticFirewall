from __future__ import annotations

import json

import pytest

from app.exceptions import Gate3GroundingException, GateException
from app.grounding import ground_quotes
from app.models import Chunk


ADVERSARIAL_FAILURES = [
    (
        "inserted word",
        "Revenue was $3M in FY2024.",
        ["Revenue definitely was $3M"],
    ),
    (
        "deleted word",
        "Revenue was exactly $3M in FY2024.",
        ["Revenue was $3M"],
    ),
    (
        "changed number",
        "Revenue was $3M.",
        ["Revenue was $4M"],
    ),
    (
        "changed currency symbol",
        "Revenue was $3M.",
        ["Revenue was €3M"],
    ),
    (
        "changed date",
        "Revenue was $3M in FY2024.",
        ["Revenue was $3M in FY2025"],
    ),
    (
        "partial beginning only with added ending",
        "Revenue was $3M.",
        ["Revenue was $3M after tax"],
    ),
    (
        "partial ending only with added beginning",
        "Revenue was $3M.",
        ["Net revenue was $3M"],
    ),
    (
        "cross paragraph inserted bridge",
        "Alpha paragraph ends.\n\nBeta paragraph starts.",
        ["Alpha paragraph ends and Beta paragraph starts"],
    ),
    (
        "ellipsis out of order",
        "FY2024 results came after the company reported revenue.",
        ["company reported...FY2024"],
    ),
    (
        "multiple ellipses out of order",
        "Alpha then Gamma then Beta.",
        ["Alpha...Beta...Gamma"],
    ),
    (
        "multiple ellipses missing middle",
        "Alpha then Gamma.",
        ["Alpha...Beta...Gamma"],
    ),
    (
        "wrong case is not a failure but changed token is",
        "Net Revenue Was $3M.",
        ["net revenue was $4m"],
    ),
    (
        "smart quotes changed content",
        "The CEO said \u201cGrowth\u201d was likely.",
        ['The CEO said "Contraction" was likely'],
    ),
    (
        "smart dash changed number",
        "Range was 3\u20134 million.",
        ["Range was 4-5 million"],
    ),
    (
        "unicode composed quote against decomposed source",
        "Cafe\u0301 revenue increased.",
        ["Café revenue increased"],
    ),
    (
        "unicode minus changed to plus",
        "Free cash flow was \u2212$1M.",
        ["Free cash flow was +$1M"],
    ),
    (
        "non-breaking space does not excuse inserted word",
        "Net\u00a0revenue was $3M.",
        ["Net reported revenue was $3M"],
    ),
    (
        "leading trailing whitespace around fabricated quote",
        "Revenue was $3M.",
        ["  Revenue was $4M  "],
    ),
    (
        "tab normalization with changed value",
        "Revenue\twas\t$3M.",
        ["Revenue was $4M"],
    ),
    (
        "newline normalization with changed value",
        "Revenue\nwas\n$3M.",
        ["Revenue was $4M"],
    ),
    (
        "quote only partially exists at prefix",
        "The product launched in April.",
        ["The product launched in April 2024"],
    ),
    (
        "quote only partially exists at suffix",
        "The product launched in April.",
        ["In 2024 the product launched in April"],
    ),
    (
        "missing punctuation cannot be invented inside token",
        "The ratio was 3.1.",
        ["The ratio was 3,1"],
    ),
    (
        "changed percentage",
        "Gross margin was 61%.",
        ["Gross margin was 16%"],
    ),
    (
        "changed unit",
        "Latency was 30 ms.",
        ["Latency was 30 seconds"],
    ),
    (
        "changed named entity",
        "Acme acquired BetaCo.",
        ["Acme acquired GammaCo"],
    ),
    (
        "changed negation",
        "The company did not issue guidance.",
        ["The company did issue guidance"],
    ),
    (
        "removed negation",
        "The company never restated results.",
        ["The company restated results"],
    ),
    (
        "added temporal qualifier",
        "Bookings increased.",
        ["Bookings increased in Q4"],
    ),
    (
        "changed quarter",
        "Bookings increased in Q3.",
        ["Bookings increased in Q4"],
    ),
    (
        "changed year embedded in token",
        "FY2024 revenue increased.",
        ["FY2025 revenue increased"],
    ),
    (
        "changed decimal",
        "ARR was $10.5M.",
        ["ARR was $10.6M"],
    ),
    (
        "changed ordinal",
        "The company ranked first.",
        ["The company ranked third"],
    ),
    (
        "changed comparative direction",
        "Expenses were lower than planned.",
        ["Expenses were higher than planned"],
    ),
    (
        "changed currency code",
        "Revenue was USD 3M.",
        ["Revenue was CAD 3M"],
    ),
    (
        "changed date format value",
        "The filing date was 2024-04-01.",
        ["The filing date was 2024-05-01"],
    ),
    (
        "ellipsis cannot reverse duplicate terms",
        "Alpha Beta Alpha Gamma.",
        ["Gamma...Beta"],
    ),
    (
        "quote cannot stitch reordered clauses",
        "Revenue rose. Expenses fell.",
        ["Expenses fell...Revenue rose"],
    ),
]


@pytest.mark.parametrize(("case_name", "raw", "quoted_spans"), ADVERSARIAL_FAILURES)
def test_adversarial_grounding_failures(case_name, raw, quoted_spans):
    with pytest.raises(Gate3GroundingException):
        ground_quotes(quoted_spans, raw)


def test_wrong_chunk_rejects_at_gate_3(storage, pipeline):
    storage.upsert_chunk(Chunk(chunk_id="chunk-1", text="Revenue was $3M."))
    storage.upsert_chunk(Chunk(chunk_id="chunk-2", text="Revenue was $4M."))
    draft = {
        "content": "Revenue was $4M.",
        "source_chunk_id": "chunk-1",
        "quoted_spans": ["Revenue was $4M"],
    }

    with pytest.raises(GateException) as exc_info:
        pipeline.process_draft(json.dumps(draft))

    assert exc_info.value.gate_number == 3


def test_duplicate_quote_uses_earliest_grounded_match():
    raw = "Revenue was $3M. Later, revenue was $3M again."
    spans = ground_quotes(["Revenue was $3M"], raw)

    assert spans[0].start_index == 0
    assert spans[0].quote == "Revenue was $3M"


def test_leading_trailing_whitespace_in_quote_is_normalized():
    raw = "Revenue was $3M."
    spans = ground_quotes(["  Revenue was $3M  "], raw)

    assert spans[0].quote == "Revenue was $3M"


def test_multiple_ellipses_pass_in_monotonic_order():
    raw = "Alpha then Beta then Gamma."
    spans = ground_quotes(["Alpha...Beta...Gamma"], raw)

    assert [span.quote for span in spans] == ["Alpha", "Beta", "Gamma"]
