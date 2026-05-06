from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


VALID_ACTIONS = {"target", "observe", "skip"}


@dataclass(frozen=True)
class GroupEvaluation:
    score: int
    classification: str
    reason: str
    action: str
    red_flags: list[str] = field(default_factory=list)
    match_signals: dict[str, Any] = field(default_factory=dict)
    model: str | None = None
    error: str | None = None

    @classmethod
    def fallback(cls, reason: str, model: str | None = None) -> GroupEvaluation:
        return cls(
            score=0,
            classification="evaluation_failed",
            reason="AI evaluation failed; candidate saved for observation.",
            action="observe",
            red_flags=[reason],
            match_signals={},
            model=model,
            error=reason,
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any], model: str) -> GroupEvaluation:
        score = int(payload.get("score", 0))
        score = max(0, min(100, score))

        action = str(payload.get("action", "observe")).strip().lower()
        if action not in VALID_ACTIONS:
            action = "observe"

        red_flags = payload.get("red_flags", [])
        if not isinstance(red_flags, list):
            red_flags = []

        match_signals = payload.get("match_signals", {})
        if not isinstance(match_signals, dict):
            match_signals = {}

        return cls(
            score=score,
            classification=str(payload.get("classification", "unknown"))[:50],
            reason=str(payload.get("reason", "")),
            action=action,
            red_flags=[str(flag) for flag in red_flags],
            match_signals=match_signals,
            model=model,
            error=None,
        )
