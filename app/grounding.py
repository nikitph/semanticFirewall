from __future__ import annotations

from app.exceptions import Gate3GroundingException
from app.models import SpanRef
from app.normalization import normalize_text


def ground_quotes(quoted_spans: list[str], chunk_text: str) -> list[SpanRef]:
    normalized_chunk, chunk_offset_map = normalize_text(chunk_text)
    span_refs: list[SpanRef] = []
    search_start = 0

    for full_quote in quoted_spans:
        segments = [segment.strip() for segment in full_quote.split("...") if segment.strip()]
        if not segments:
            raise Gate3GroundingException(
                "Quoted segment not found in source chunk.",
                {
                    "missing_segment": full_quote,
                    "full_quote": full_quote,
                    "normalized_missing_segment": "",
                },
            )

        for segment in segments:
            normalized_segment, _ = normalize_text(segment)
            match_start = normalized_chunk.find(normalized_segment, search_start)
            if match_start < 0:
                raise Gate3GroundingException(
                    "Quoted segment not found in source chunk.",
                    {
                        "missing_segment": segment,
                        "full_quote": full_quote,
                        "normalized_missing_segment": normalized_segment,
                    },
                )

            match_end = match_start + len(normalized_segment)
            raw_start = chunk_offset_map[match_start]
            raw_end = chunk_offset_map[match_end - 1] + 1
            raw_quote = chunk_text[raw_start:raw_end]
            span_ref = SpanRef(start_index=raw_start, end_index=raw_end, quote=raw_quote)
            assert chunk_text[span_ref.start_index : span_ref.end_index] == span_ref.quote
            span_refs.append(span_ref)
            search_start = match_end

    return span_refs
