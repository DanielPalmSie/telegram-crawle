from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.models.candidate import TelegramCandidate
from app.models.evaluation import GroupEvaluation

logger = structlog.get_logger(__name__)


class TelegramGroupRepository:
    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(database_url, pool_pre_ping=True)

    def save_evaluated_candidate(
        self,
        candidate: TelegramCandidate,
        evaluation: GroupEvaluation,
    ) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        payload = self._payload(candidate, evaluation, now)

        with self._engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT id
                    FROM telegram_group
                    WHERE (:telegram_chat_id IS NOT NULL AND telegram_chat_id = :telegram_chat_id)
                       OR (:username IS NOT NULL AND LOWER(username) = LOWER(:username))
                    LIMIT 1
                    """
                ),
                {
                    "telegram_chat_id": candidate.telegram_chat_id,
                    "username": candidate.username,
                },
            ).first()

            if row is None:
                connection.execute(_INSERT_SQL, payload)
                logger.info("telegram_group_inserted", group=candidate.stable_key)
                return

            connection.execute(_UPDATE_SQL, {"id": row.id, **payload})
            logger.info("telegram_group_updated", group=candidate.stable_key, id=row.id)

    def _payload(
        self,
        candidate: TelegramCandidate,
        evaluation: GroupEvaluation,
        now: datetime,
    ) -> dict[str, Any]:
        raw_metadata = {
            **candidate.raw_metadata,
            "sample_messages": candidate.sample_messages,
        }

        return {
            "telegram_chat_id": candidate.telegram_chat_id,
            "username": candidate.username[:64] if candidate.username else None,
            "invite_link": candidate.invite_link[:255] if candidate.invite_link else None,
            "title": candidate.title[:255],
            "description": candidate.description,
            "member_count": candidate.member_count,
            "source": candidate.source[:64] if candidate.source else None,
            "evaluation_status": "failed" if evaluation.error else "done",
            "evaluation_score": evaluation.score,
            "classification": evaluation.classification[:50],
            "evaluation_reason": evaluation.reason,
            "evaluation_model": evaluation.model[:64] if evaluation.model else None,
            "evaluation_error": evaluation.error,
            "evaluated_at": now,
            "action": evaluation.action[:20],
            "priority": evaluation.score,
            "match_signals": json.dumps(evaluation.match_signals, ensure_ascii=True),
            "raw_metadata": json.dumps(raw_metadata, ensure_ascii=True),
            "now": now,
        }


_INSERT_SQL = text(
    """
    INSERT INTO telegram_group (
        telegram_chat_id,
        username,
        invite_link,
        title,
        description,
        member_count,
        source,
        evaluation_status,
        evaluation_score,
        classification,
        evaluation_reason,
        evaluation_model,
        evaluation_error,
        evaluated_at,
        action,
        priority,
        match_signals,
        raw_metadata,
        first_seen_at,
        last_seen_at,
        last_crawled_at,
        created_at,
        updated_at
    ) VALUES (
        :telegram_chat_id,
        :username,
        :invite_link,
        :title,
        :description,
        :member_count,
        :source,
        :evaluation_status,
        :evaluation_score,
        :classification,
        :evaluation_reason,
        :evaluation_model,
        :evaluation_error,
        :evaluated_at,
        :action,
        :priority,
        CAST(:match_signals AS JSON),
        CAST(:raw_metadata AS JSON),
        :now,
        :now,
        :now,
        :now,
        :now
    )
    """
)

_UPDATE_SQL = text(
    """
    UPDATE telegram_group
    SET telegram_chat_id = COALESCE(:telegram_chat_id, telegram_chat_id),
        username = COALESCE(:username, username),
        invite_link = :invite_link,
        title = :title,
        description = :description,
        member_count = :member_count,
        source = :source,
        evaluation_status = :evaluation_status,
        evaluation_score = :evaluation_score,
        classification = :classification,
        evaluation_reason = :evaluation_reason,
        evaluation_model = :evaluation_model,
        evaluation_error = :evaluation_error,
        evaluated_at = :evaluated_at,
        action = :action,
        priority = :priority,
        match_signals = CAST(:match_signals AS JSON),
        raw_metadata = CAST(:raw_metadata AS JSON),
        last_seen_at = :now,
        last_crawled_at = :now,
        updated_at = :now
    WHERE id = :id
    """
)
