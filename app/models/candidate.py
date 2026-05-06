from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TelegramCandidate:
    title: str
    telegram_chat_id: int | None = None
    username: str | None = None
    invite_link: str | None = None
    description: str | None = None
    member_count: int | None = None
    source: str | None = None
    sample_messages: list[str] = field(default_factory=list)
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def stable_key(self) -> str:
        if self.telegram_chat_id is not None:
            return f"id:{self.telegram_chat_id}"
        if self.username:
            return f"username:{self.username.lower()}"
        return f"title:{self.title.lower()}"
