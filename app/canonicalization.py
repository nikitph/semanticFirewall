from __future__ import annotations

import json
import re
from typing import Protocol

from pydantic import ValidationError

from app.exceptions import Gate4CanonicalizationException
from app.models import CanonicalClaim


class Canonicalizer(Protocol):
    def canonicalize(self, content: str) -> CanonicalClaim:
        ...


class MockCanonicalizer:
    def canonicalize(self, content: str) -> CanonicalClaim:
        return CanonicalClaim(
            subject="unknown",
            predicate="states",
            object=content.strip(),
            temporal_bound=None,
        )


class RuleCanonicalizer:
    def canonicalize(self, content: str) -> CanonicalClaim:
        text = content.strip()
        normalized = " ".join(text.rstrip(".").split())

        revenue_match = re.fullmatch(
            r"(?P<subject>net revenue|revenue|arr|gross margin) was (?P<object>.+?)(?: in (?P<time>FY\d{4}|Q[1-4]|20\d{2}))?",
            normalized,
            flags=re.IGNORECASE,
        )
        if revenue_match:
            return CanonicalClaim(
                subject=revenue_match.group("subject").lower(),
                predicate="equals",
                object=_normalize_object(revenue_match.group("object")),
                temporal_bound=revenue_match.group("time"),
            )

        acquisition_match = re.fullmatch(
            r"(?P<subject>[A-Za-z0-9 ._-]+) acquired (?P<object>[A-Za-z0-9 ._-]+)",
            normalized,
            flags=re.IGNORECASE,
        )
        if acquisition_match:
            return CanonicalClaim(
                subject=acquisition_match.group("subject").strip().lower(),
                predicate="acquired",
                object=acquisition_match.group("object").strip().lower(),
                temporal_bound=None,
            )

        increase_match = re.fullmatch(
            r"(?P<subject>[A-Za-z0-9 ._-]+) increased(?: in (?P<time>Q[1-4]|FY\d{4}|20\d{2}))?",
            normalized,
            flags=re.IGNORECASE,
        )
        if increase_match:
            return CanonicalClaim(
                subject=increase_match.group("subject").strip().lower(),
                predicate="increased",
                object="true",
                temporal_bound=increase_match.group("time"),
            )

        return CanonicalClaim(
            subject="unknown",
            predicate="states",
            object=normalized,
            temporal_bound=None,
        )


class LLMCanonicalizer:
    def __init__(self, client: object):
        self.client = client

    def canonicalize(self, content: str) -> CanonicalClaim:
        raise Gate4CanonicalizationException(
            "LLM canonicalizer is not configured for this offline implementation.",
            {"content": content},
        )


def canonical_claim_from_json(raw_json: str) -> CanonicalClaim:
    try:
        data = json.loads(raw_json)
        return CanonicalClaim.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise Gate4CanonicalizationException(
            "Canonicalization output failed validation.",
            {"error": str(exc)},
        ) from exc


def _normalize_object(value: str) -> str:
    value = value.strip()
    amount_match = re.fullmatch(r"\$(\d+(?:\.\d+)?)([mkb])", value, flags=re.IGNORECASE)
    if amount_match:
        return f"${amount_match.group(1)}{amount_match.group(2).upper()}"
    return value.lower()
