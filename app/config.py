from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import structlog
from dotenv import load_dotenv


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


@dataclass(frozen=True)
class Settings:
    telegram_api_id: int
    telegram_api_hash: str
    openai_api_key: str
    database_url: str
    keywords: list[str]
    log_level: str
    openai_model: str
    crawler_interval_seconds: int
    crawler_search_limit: int
    crawler_message_sample_limit: int
    telegram_request_delay_seconds: float
    telegram_keyword_delay_seconds: float
    telegram_session: str | None
    telegram_session_file: str

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()

        missing = [
            name
            for name in (
                "TELEGRAM_API_ID",
                "TELEGRAM_API_HASH",
                "OPENAI_API_KEY",
                "DATABASE_URL",
            )
            if not os.getenv(name)
        ]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required environment variables: {joined}")

        keywords = _split_csv(os.getenv("CRAWLER_KEYWORDS", ""))
        if not keywords:
            raise ValueError("CRAWLER_KEYWORDS must include at least one keyword")

        telegram_session_name = os.getenv("TELEGRAM_SESSION_NAME", "telegram-crawler")

        return cls(
            telegram_api_id=_get_int("TELEGRAM_API_ID", 0),
            telegram_api_hash=os.environ["TELEGRAM_API_HASH"],
            openai_api_key=os.environ["OPENAI_API_KEY"],
            database_url=os.environ["DATABASE_URL"],
            keywords=keywords,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            crawler_interval_seconds=_get_int(
                "CRAWLER_INTERVAL_SECONDS",
                _get_int("CRAWLER_INTERVAL_MINUTES", 60) * 60,
            ),
            crawler_search_limit=_get_int("CRAWLER_SEARCH_LIMIT", 20),
            crawler_message_sample_limit=_get_int("CRAWLER_MESSAGE_SAMPLE_LIMIT", 5),
            telegram_request_delay_seconds=_get_float("TELEGRAM_REQUEST_DELAY_SECONDS", 3.0),
            telegram_keyword_delay_seconds=_get_float("TELEGRAM_KEYWORD_DELAY_SECONDS", 10.0),
            telegram_session=os.getenv("TELEGRAM_SESSION") or None,
            telegram_session_file=os.getenv(
                "TELEGRAM_SESSION_FILE",
                str(Path.cwd() / "session" / telegram_session_name),
            ),
        )


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level, logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level, logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
