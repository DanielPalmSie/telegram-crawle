from __future__ import annotations

import argparse
import asyncio
import signal

import structlog
from telethon import TelegramClient

from app.ai.evaluator import OpenAIGroupEvaluator
from app.config import Settings, configure_logging
from app.crawler.telegram_client import TelegramDiscoveryClient
from app.storage.telegram_group_repository import TelegramGroupRepository

logger = structlog.get_logger(__name__)


async def run_login(settings: Settings) -> None:
    client = TelegramClient(
        settings.telegram_session_file,
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )
    await client.start()
    await client.disconnect()
    logger.info("telegram_session_authorized", session_file=settings.telegram_session_file)


async def crawl_once(settings: Settings) -> None:
    evaluator = OpenAIGroupEvaluator(settings.openai_api_key, settings.openai_model)
    repository = TelegramGroupRepository(settings.database_url)

    async with TelegramDiscoveryClient(settings) as telegram:
        for keyword in settings.keywords:
            async for candidate in telegram.search_public_groups(keyword):
                evaluation = evaluator.evaluate(candidate)
                repository.save_evaluated_candidate(candidate, evaluation)

            await asyncio.sleep(settings.telegram_keyword_delay_seconds)


async def run_forever(settings: Settings) -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), stop_event.set)

    logger.info(
        "crawler_started",
        interval_seconds=settings.crawler_interval_seconds,
        keywords=settings.keywords,
    )

    while not stop_event.is_set():
        try:
            await crawl_once(settings)
            logger.info("crawler_cycle_completed")
        except Exception as exc:  # noqa: BLE001 - keep background service alive
            logger.exception("crawler_cycle_failed", error=str(exc))

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.crawler_interval_seconds)
        except TimeoutError:
            continue

    logger.info("crawler_stopped")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram group discovery crawler")
    parser.add_argument(
        "--login",
        action="store_true",
        help="authorize and persist a Telegram session file",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="run one crawler cycle and exit",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = Settings.from_env()
    configure_logging(settings.log_level)

    if args.login:
        asyncio.run(run_login(settings))
        return

    if args.once:
        asyncio.run(crawl_once(settings))
        return

    asyncio.run(run_forever(settings))


if __name__ == "__main__":
    main()
