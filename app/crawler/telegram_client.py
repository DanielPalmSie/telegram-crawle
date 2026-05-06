from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import structlog
from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession

from app.config import Settings
from app.models.candidate import TelegramCandidate

logger = structlog.get_logger(__name__)


class TelegramDiscoveryClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        session = (
            StringSession(settings.telegram_session)
            if settings.telegram_session
            else settings.telegram_session_file
        )
        if not settings.telegram_session:
            Path(settings.telegram_session_file).parent.mkdir(parents=True, exist_ok=True)

        self._client = TelegramClient(
            session,
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )

    async def __aenter__(self) -> TelegramDiscoveryClient:
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise RuntimeError(
                "Telegram session is not authorized. Run `python -m app.main --login` "
                "locally to create a session, then set TELEGRAM_SESSION for Docker."
            )
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self._client.disconnect()

    async def search_public_groups(self, keyword: str) -> AsyncIterator[TelegramCandidate]:
        logger.info("telegram_keyword_search_started", keyword=keyword)

        result = await self._client(
            functions.contacts.SearchRequest(
                q=keyword,
                limit=self._settings.crawler_search_limit,
            )
        )
        await asyncio.sleep(self._settings.telegram_request_delay_seconds)

        chats = getattr(result, "chats", [])
        logger.info(
            "telegram_keyword_search_completed",
            keyword=keyword,
            groups_found=len(chats),
        )

        seen: set[str] = set()
        for entity in chats:
            if not self._is_public_group(entity):
                continue

            candidate = await self._candidate_from_entity(entity, source=f"telegram:{keyword}")
            if candidate.stable_key in seen:
                continue

            seen.add(candidate.stable_key)
            yield candidate

    async def _candidate_from_entity(
        self,
        entity: types.TypeChat,
        source: str,
    ) -> TelegramCandidate:
        description, member_count = await self._load_group_details(entity)
        sample_messages = await self._load_sample_messages(entity)

        username = getattr(entity, "username", None)
        invite_link = f"https://t.me/{username}" if username else None
        telegram_chat_id = getattr(entity, "id", None)

        return TelegramCandidate(
            title=getattr(entity, "title", "") or "Untitled Telegram group",
            telegram_chat_id=int(telegram_chat_id) if telegram_chat_id is not None else None,
            username=username,
            invite_link=invite_link,
            description=description,
            member_count=member_count,
            source=source,
            sample_messages=sample_messages,
            raw_metadata={
                "telegram_entity_type": entity.__class__.__name__,
                "access_hash_present": getattr(entity, "access_hash", None) is not None,
                "megagroup": getattr(entity, "megagroup", None),
                "broadcast": getattr(entity, "broadcast", None),
                "verified": getattr(entity, "verified", None),
                "restricted": getattr(entity, "restricted", None),
            },
        )

    async def _load_group_details(self, entity: types.TypeChat) -> tuple[str | None, int | None]:
        try:
            if isinstance(entity, types.Channel):
                full = await self._client(functions.channels.GetFullChannelRequest(entity))
                await asyncio.sleep(self._settings.telegram_request_delay_seconds)
                full_chat = full.full_chat
                return (
                    getattr(full_chat, "about", None),
                    getattr(full_chat, "participants_count", None),
                )

            if isinstance(entity, types.Chat):
                full = await self._client(functions.messages.GetFullChatRequest(entity.id))
                await asyncio.sleep(self._settings.telegram_request_delay_seconds)
                full_chat = full.full_chat
                return (
                    getattr(full_chat, "about", None),
                    getattr(full_chat, "participants_count", None),
                )
        except Exception as exc:  # noqa: BLE001 - Telegram access varies by group
            logger.warning(
                "telegram_group_details_unavailable",
                group=getattr(entity, "username", None) or getattr(entity, "id", None),
                error=str(exc),
            )

        return None, getattr(entity, "participants_count", None)

    async def _load_sample_messages(self, entity: types.TypeChat) -> list[str]:
        messages: list[str] = []
        try:
            async for message in self._client.iter_messages(
                entity,
                limit=self._settings.crawler_message_sample_limit,
            ):
                text = getattr(message, "message", None)
                if text:
                    messages.append(text[:500])
            await asyncio.sleep(self._settings.telegram_request_delay_seconds)
        except Exception as exc:  # noqa: BLE001 - public metadata can still block messages
            logger.warning(
                "telegram_messages_unavailable",
                group=getattr(entity, "username", None) or getattr(entity, "id", None),
                error=str(exc),
            )

        return messages

    def _is_public_group(self, entity: Any) -> bool:
        if isinstance(entity, types.Channel):
            return bool(getattr(entity, "username", None)) and bool(
                getattr(entity, "megagroup", False)
            )

        if isinstance(entity, types.Chat):
            return bool(getattr(entity, "username", None))

        return False
