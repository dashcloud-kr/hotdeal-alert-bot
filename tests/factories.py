"""PTB Update/Context 테스트 팩토리."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from telegram import Bot, Update


def make_bot() -> MagicMock:
    """네트워크 호출 없이 send_message 를 기록하는 가짜 Bot."""
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
    return bot


def make_message_update(
    text: str = "/start",
    *,
    user_id: int = 100,
    chat_id: int = 100,
    chat_type: str = "private",
    first_name: str = "테스터",
    update_id: int = 1,
) -> Update:
    data = {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "date": int(datetime.now(UTC).timestamp()),
            "chat": {"id": chat_id, "type": chat_type},
            "from": {"id": user_id, "is_bot": False, "first_name": first_name},
            "text": text,
        },
    }
    update = Update.de_json(data, bot=make_bot())
    assert update is not None
    return update


def make_context(
    *,
    args: list[str] | None = None,
    bot_data: dict | None = None,
    error: BaseException | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        bot=make_bot(),
        args=args or [],
        bot_data=bot_data or {},
        user_data={},
        chat_data={},
        error=error,
    )
