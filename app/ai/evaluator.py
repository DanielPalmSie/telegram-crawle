from __future__ import annotations

import json
from typing import Any

import structlog
from openai import OpenAI

from app.models.candidate import TelegramCandidate
from app.models.evaluation import GroupEvaluation

logger = structlog.get_logger(__name__)


EVALUATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "classification": {"type": "string"},
        "reason": {"type": "string"},
        "action": {"type": "string", "enum": ["target", "observe", "skip"]},
        "red_flags": {"type": "array", "items": {"type": "string"}},
        "match_signals": {
            "type": "object",
            "additionalProperties": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "number"},
                    {"type": "boolean"},
                    {"type": "array", "items": {"type": "string"}},
                ]
            },
        },
    },
    "required": [
        "score",
        "classification",
        "reason",
        "action",
        "red_flags",
        "match_signals",
    ],
}


SYSTEM_PROMPT = """You evaluate public Telegram groups for a read-only community discovery crawler.

The service only discovers public communities, ranks/filter them, and stores metadata.
It must not support spam, auto-messaging, aggressive joining, or illegal scraping.

Useful target groups:
- help, advice, and community support
- relocation, life, and expat support
- question-answer interactions where members help each other

Reject or down-rank:
- jobs-only groups
- apartment-only groups
- spam or link farms
- crypto, trading, and investment groups
- random chat without practical support value
- dating
- marketplaces and buy/sell groups

Return strict JSON only."""


class OpenAIGroupEvaluator:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def evaluate(self, candidate: TelegramCandidate) -> GroupEvaluation:
        try:
            payload = self._evaluate_with_responses_api(candidate)
            evaluation = GroupEvaluation.from_payload(payload, self._model)
            logger.info(
                "ai_evaluation_completed",
                group=candidate.stable_key,
                score=evaluation.score,
                action=evaluation.action,
                classification=evaluation.classification,
            )
            return evaluation
        except Exception as exc:  # noqa: BLE001 - external API fallback boundary
            logger.exception(
                "ai_evaluation_failed",
                group=candidate.stable_key,
                error=str(exc),
            )
            return GroupEvaluation.fallback(str(exc), model=self._model)

    def _evaluate_with_responses_api(self, candidate: TelegramCandidate) -> dict[str, Any]:
        response = self._client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "title": candidate.title,
                            "username": candidate.username,
                            "description": candidate.description,
                            "member_count": candidate.member_count,
                            "sample_recent_messages": candidate.sample_messages,
                        },
                        ensure_ascii=True,
                    ),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "telegram_group_evaluation",
                    "schema": EVALUATION_SCHEMA,
                    "strict": True,
                }
            },
        )

        output_text = getattr(response, "output_text", None)
        if not output_text:
            raise ValueError("OpenAI response did not include output_text")

        payload = json.loads(output_text)
        if not isinstance(payload, dict):
            raise ValueError("OpenAI response JSON is not an object")

        return payload
