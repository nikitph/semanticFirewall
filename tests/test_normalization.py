from __future__ import annotations

from app.normalization import normalize_text


def test_normalizes_case_whitespace_and_smart_punctuation():
    raw = "Net\n revenue   was \u201c$4M\u201d \u2014 in FY2024."
    normalized, offset_map = normalize_text(raw)

    assert normalized == 'net revenue was "$4m" - in fy2024.'
    assert len(normalized) == len(offset_map)
    recovered_start = offset_map[normalized.index("revenue")]
    assert raw[recovered_start:].startswith("revenue")


def test_normalizes_tabs_non_breaking_space_and_trims():
    raw = "\t Alpha\u00a0\u00a0Beta\n\nGamma  "
    normalized, offset_map = normalize_text(raw)

    assert normalized == "alpha beta gamma"
    assert len(normalized) == len(offset_map)
    assert raw[offset_map[5]] == "\u00a0"


def test_unicode_is_preserved_except_lowercase_and_spacing():
    raw = "  CAFÉ\tΔelta  "
    normalized, offset_map = normalize_text(raw)

    assert normalized == "café δelta"
    assert len(normalized) == len(offset_map)
