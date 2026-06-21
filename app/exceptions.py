from __future__ import annotations

from typing import Any


class GateException(Exception):
    gate_number: int = 0

    def __init__(self, reason: str, details: dict[str, Any] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


class Gate1ParseException(GateException):
    gate_number = 1


class Gate2SchemaException(GateException):
    gate_number = 2


class Gate3GroundingException(GateException):
    gate_number = 3


class Gate4CanonicalizationException(GateException):
    gate_number = 4


class Gate5CommitException(GateException):
    gate_number = 5
