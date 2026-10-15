"""핫딜 명령어와 백그라운드 잡."""

from __future__ import annotations

import logging

import httpx
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import CommandHandler, ContextTypes

from app.services.matching import matches
from app.services.repository import Repository
from app.services.rss import HotdealItem, now_iso, parse_rss_items
from app.services.sources import SOURCES
from app.utils.format import (
    format_digest_messages,
    format_item_message,
    format_price_range,
)
from app.utils.parse import parse_price_range

logger = logging.getLogger(__name__)

INCLUDE_LIMIT = 20
EXCLUDE_LIMIT = 10
LATEST_COUNT = 5

POLL_INTERVAL_SECONDS = 300
DIGEST_INTERVAL_SECONDS = 3600

MODE_LABELS = {"realtime": "실시간", "digest": "다이제스트(1시간 모아보기)"}
MODE_ALIASES = {
    "realtime": "realtime",
    "실시간": "realtime",
    "digest": "digest",
    "다이제스트": "digest",
    "모아보기": "digest",
}

HOTDEAL_HELP = """핫딜 알림 봇 — 명령어 목록

/add 아이패드 에어팟 — 알림 받을 키워드 (없으면 전체 수신)
/ban 중고 리퍼 — 제외 키워드
/keywords — 키워드 목록
/del 아이패드 — 키워드 삭제

/mode realtime — 실시간 알림 (기본)
/mode digest — 1시간마다 모아서 알림
/price 1만-5만 — 가격 범위 필터 (5만-, -3만 가능)
/price off — 가격 필터 해제

/latest — 최신 핫딜 5건 미리보기
/settings — 내 설정 요약
/status — 봇 상태 · /id — 내 chat id

출처: 뽐뿌 핫딜 게시판 (5분마다 확인)"""


def handlers() -> list[CommandHandler]:
    return [
        CommandHandler("add", cmd_add),
        CommandHandler("ban", cmd_ban),
        CommandHandler("keywords", cmd_keywords),
        CommandHandler("del", cmd_del),
        CommandHandler("mode", cmd_mode),
        CommandHandler("price", cmd_price),
        CommandHandler("latest", cmd_latest),
        CommandHandler("settings", cmd_settings),
    ]


# ---- 내부 헬퍼 -------------------------------------------------------------


def _repo(context: ContextTypes.DEFAULT_TYPE) -> Repository:
    return context.bot_data["repo"]


def _ids(update: Update) -> tuple[int, int] | None:
    if update.effective_user is None or update.effective_chat is None:
        return None
    return update.effective_user.id, update.effective_chat.id


async def _say(update: Update, text: str) -> None:
    if update.effective_message is not None:
        await update.effective_message.reply_text(text)


# ---- 명령어 ----------------------------------------------------------------


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ids = _ids(update)
    if ids is None:
        return
    user_id, chat_id = ids
    if not context.args:
        await _say(update, "사용법: /add 아이패드 에어팟 (여러 개 가능)")
        return

    repo = _repo(context)
    includes, _ = await repo.list_keywords(user_id, chat_id)
    added: list[str] = []
    skipped: list[str] = []
    for keyword in context.args[:INCLUDE_LIMIT]:
        if keyword in includes or keyword in added:
            skipped.append(f"{keyword}(중복)")
            continue
        if len(includes) + len(added) >= INCLUDE_LIMIT:
            skipped.append(f"{keyword}(최대 {INCLUDE_LIMIT}개)")
            continue
        await repo.add_keyword(user_id, chat_id, "include", keyword)
        added.append(keyword)

    lines = []
    if added:
        lines.append(f"키워드 추가: {', '.join(added)}")
    if skipped:
        lines.append(f"제외: {', '.join(skipped)}")
    if not lines:
        lines.append("추가된 키워드가 없습니다.")
    await _say(update, "\n".join(lines))


async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ids = _ids(update)
    if ids is None:
        return
    user_id, chat_id = ids
    if not context.args:
        await _say(update, "사용법: /ban 중고 리퍼 (제목에 포함되면 제외)")
        return

    repo = _repo(context)
    _, excludes = await repo.list_keywords(user_id, chat_id)
    added: list[str] = []
    skipped: list[str] = []
    for keyword in context.args[:EXCLUDE_LIMIT]:
        if keyword in excludes or keyword in added:
            skipped.append(f"{keyword}(중복)")
            continue
        if len(excludes) + len(added) >= EXCLUDE_LIMIT:
            skipped.append(f"{keyword}(최대 {EXCLUDE_LIMIT}개)")
            continue
        await repo.add_keyword(user_id, chat_id, "exclude", keyword)
        added.append(keyword)

    lines = []
    if added:
        lines.append(f"제외 키워드 추가: {', '.join(added)}")
    if skipped:
        lines.append(f"제외: {', '.join(skipped)}")
    if not lines:
        lines.append("추가된 키워드가 없습니다.")
    await _say(update, "\n".join(lines))


async def cmd_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ids = _ids(update)
    if ids is None:
        return
    user_id, chat_id = ids
    includes, excludes = await _repo(context).list_keywords(user_id, chat_id)
    lines = [
        f"포함 키워드 ({len(includes)}/{INCLUDE_LIMIT}): "
        + (", ".join(includes) if includes else "없음 — 전체 수신"),
        f"제외 키워드 ({len(excludes)}/{EXCLUDE_LIMIT}): "
        + (", ".join(excludes) if excludes else "없음"),
    ]
    await _say(update, "\n".join(lines))


async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ids = _ids(update)
    if ids is None:
        return
    user_id, chat_id = ids
    if not context.args:
        await _say(update, "사용법: /del 아이패드")
        return
    keyword = context.args[0]
    removed = await _repo(context).remove_keyword(user_id, chat_id, keyword)
    message = f"'{keyword}' 삭제했습니다." if removed else f"'{keyword}' 키워드가 없습니다."
    await _say(update, message)


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ids = _ids(update)
    if ids is None:
        return
    user_id, chat_id = ids
    repo = _repo(context)
    if not context.args:
        settings = await repo.get_settings(user_id, chat_id)
        await _say(
            update,
            f"현재 모드: {MODE_LABELS.get(settings.mode, settings.mode)}\n"
            "사용법: /mode realtime 또는 /mode digest",
        )
        return
    mode = MODE_ALIASES.get(context.args[0].lower())
    if mode is None:
        await _say(update, "realtime(실시간) 또는 digest(모아보기)만 가능합니다.")
        return
    await repo.set_mode(user_id, chat_id, mode)
    await _say(update, f"알림 모드: {MODE_LABELS[mode]}")


async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ids = _ids(update)
    if ids is None:
        return
    user_id, chat_id = ids
    repo = _repo(context)
    if not context.args:
        settings = await repo.get_settings(user_id, chat_id)
        await _say(
            update,
            f"가격 필터: {format_price_range(settings.min_price, settings.max_price)}\n"
            "사용법: /price 1만-5만 · /price 5만- · /price -3만 · /price off",
        )
        return
    parsed = parse_price_range(" ".join(context.args))
    if parsed is None:
        await _say(update, "가격 범위를 인식하지 못했습니다. 예: /price 1만-5만, /price off")
        return
    min_price, max_price = parsed
    await repo.set_price_range(user_id, chat_id, min_price, max_price)
    if min_price is None and max_price is None:
        await _say(update, "가격 필터를 해제했습니다.")
    else:
        await _say(update, f"가격 필터: {format_price_range(min_price, max_price)}")


async def cmd_latest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    items = await _repo(context).recent_items(LATEST_COUNT)
    if not items:
        await _say(update, "아직 수집된 핫딜이 없습니다. 잠시 후 다시 시도하세요.")
        return
    await _say(update, f"최신 핫딜 {len(items)}건")
    for item in items:
        await _say(update, format_item_message(item))


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ids = _ids(update)
    if ids is None:
        return
    user_id, chat_id = ids
    repo = _repo(context)
    includes, excludes = await repo.list_keywords(user_id, chat_id)
    settings = await repo.get_settings(user_id, chat_id)
    lines = [
        "내 설정",
        f"모드: {MODE_LABELS.get(settings.mode, settings.mode)}",
        f"가격: {format_price_range(settings.min_price, settings.max_price)}",
        "포함 키워드: " + (", ".join(includes) if includes else "없음 (전체 수신)"),
        "제외 키워드: " + (", ".join(excludes) if excludes else "없음"),
    ]
    await _say(update, "\n".join(lines))


# ---- 백그라운드 잡 ---------------------------------------------------------


async def poll_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """5분마다 RSS를 확인해 새 핫딜을 필터에 맞는 구독자에게 보낸다."""
    repo = _repo(context)
    client = context.bot_data["rss"]

    bootstrap = await repo.count_items() == 0

    collected: list[HotdealItem] = []
    for source in SOURCES:
        try:
            xml = await client.fetch(source.url)
        except httpx.HTTPError:
            logger.warning("RSS 수집 실패: %s", source.name, exc_info=True)
            continue
        collected.extend(parse_rss_items(xml, source.name))

    if not collected:
        return

    now = now_iso()
    if bootstrap:
        # 첫 실행: 기존 글은 알림 없이 등록만 (구독 직후 과거 글 폭탄 방지)
        for item in collected:
            await repo.insert_item(item, now)
        await repo.mark_processed([item.guid for item in collected], now)
        logger.info("부트스트랩: %d건 등록 (알림 없음)", len(collected))
        return

    for item in collected:
        await repo.insert_item(item, now)

    unprocessed = await repo.unprocessed_items()
    if not unprocessed:
        return

    subscribers = await repo.all_subscribers()
    for item in unprocessed:
        for user_id, chat_id in subscribers:
            filters = await repo.filters_for(user_id, chat_id)
            if not matches(item, filters):
                continue
            settings = await repo.get_settings(user_id, chat_id)
            if settings.mode == "digest":
                await repo.enqueue_digest(chat_id, item.guid, now)
            else:
                await _notify(context, chat_id, format_item_message(item))
        await repo.mark_processed([item.guid], now)


async def digest_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """1시간마다 다이제스트 모드 구독자에게 모아둔 핫딜을 보낸다."""
    repo = _repo(context)
    rows = await repo.drain_digest()
    if not rows:
        return

    by_chat: dict[int, list[HotdealItem]] = {}
    for chat_id, item in rows:
        by_chat.setdefault(chat_id, []).append(item)

    for chat_id, items in by_chat.items():
        for chunk in format_digest_messages(items):
            await _notify(context, chat_id, chunk)
        await repo.clear_digest(chat_id, [item.guid for item in items])


async def _notify(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str) -> None:
    try:
        await context.bot.send_message(chat_id=chat_id, text=text)
    except TelegramError:
        logger.warning("알림 전송 실패 (chat_id=%s)", chat_id, exc_info=True)
