"""hotdeal-alert-bot 엔트리포인트.

뽐뿌 핫딜 게시판을 5분마다 확인해 키워드·가격 필터에 맞는 핫딜만
실시간 또는 다이제스트로 알려주는 24/7 텔레그램 봇.
"""

from __future__ import annotations

import logging

import httpx
from dotenv import load_dotenv
from telegram import BotCommand, Update

from app.bot import build_application
from app.clients.rss import RssClient
from app.config import Config
from app.handlers import hotdeal
from app.services.repository import Repository

MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS items (
      guid TEXT PRIMARY KEY,
      source TEXT NOT NULL,
      title TEXT NOT NULL,
      link TEXT NOT NULL,
      description TEXT,
      price REAL,
      published_at TEXT,
      fetched_at TEXT NOT NULL,
      processed_at TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS keywords (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      chat_id INTEGER NOT NULL,
      kind TEXT NOT NULL CHECK (kind IN ('include', 'exclude')),
      keyword TEXT NOT NULL,
      UNIQUE (user_id, chat_id, kind, keyword)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
      user_id INTEGER NOT NULL,
      chat_id INTEGER NOT NULL,
      mode TEXT NOT NULL DEFAULT 'realtime' CHECK (mode IN ('realtime', 'digest')),
      min_price REAL,
      max_price REAL,
      PRIMARY KEY (user_id, chat_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS digest_queue (
      chat_id INTEGER NOT NULL,
      guid TEXT NOT NULL,
      queued_at TEXT NOT NULL,
      PRIMARY KEY (chat_id, guid)
    );
    """,
]

COMMANDS = [
    BotCommand("add", "알림 키워드 추가"),
    BotCommand("ban", "제외 키워드 추가"),
    BotCommand("keywords", "키워드 목록"),
    BotCommand("del", "키워드 삭제"),
    BotCommand("mode", "실시간/다이제스트 모드"),
    BotCommand("price", "가격 범위 필터"),
    BotCommand("latest", "최신 핫딜 미리보기"),
    BotCommand("settings", "내 설정 요약"),
    BotCommand("start", "시작"),
    BotCommand("help", "명령어 목록"),
    BotCommand("status", "봇 상태"),
    BotCommand("id", "내 chat id"),
]


async def setup(application) -> None:
    http = httpx.AsyncClient(timeout=20.0)
    application.bot_data["http"] = http
    application.bot_data["rss"] = RssClient(http)
    application.bot_data["repo"] = Repository(application.bot_data["db"])


async def teardown(application) -> None:
    http: httpx.AsyncClient | None = application.bot_data.get("http")
    if http is not None:
        await http.aclose()


def main() -> None:
    load_dotenv()
    config = Config.from_env()
    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    application = build_application(
        config,
        migrations=MIGRATIONS,
        extra_handlers=hotdeal.handlers(),
        help_text=hotdeal.HOTDEAL_HELP,
        commands=COMMANDS,
        setup=setup,
        teardown=teardown,
    )
    application.job_queue.run_repeating(
        hotdeal.poll_job,
        interval=hotdeal.POLL_INTERVAL_SECONDS,
        first=20,
        name="poll",
    )
    application.job_queue.run_repeating(
        hotdeal.digest_job,
        interval=hotdeal.DIGEST_INTERVAL_SECONDS,
        first=300,
        name="digest",
    )
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
