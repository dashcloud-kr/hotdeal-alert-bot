"""핫딜 명령어 핸들러 테스트."""

from __future__ import annotations

from app.handlers import hotdeal
from tests.factories import make_context, make_message_update
from tests.test_repository import make_item


def _ctx(update, repo):
    message = update.effective_message
    args = message.text.split()[1:] if message is not None and message.text else []
    return make_context(args=args, bot_data={"repo": repo})


def _texts(update) -> list[str]:
    return [call.kwargs["text"] for call in update.get_bot().send_message.await_args_list]


def _last(update) -> str:
    return _texts(update)[-1]


# ---- /add -------------------------------------------------------------------


async def test_add_키워드(repo):
    update = make_message_update("/add 아이패드 에어팟")
    await hotdeal.cmd_add(update, _ctx(update, repo))
    assert "키워드 추가: 아이패드, 에어팟" in _last(update)
    includes, _ = await repo.list_keywords(100, 100)
    assert includes == ["아이패드", "에어팟"]


async def test_add_중복과_사용법(repo):
    update = make_message_update("/add")
    await hotdeal.cmd_add(update, _ctx(update, repo))
    assert "사용법" in _last(update)

    await repo.add_keyword(100, 100, "include", "아이패드")
    update = make_message_update("/add 아이패드")
    await hotdeal.cmd_add(update, _ctx(update, repo))
    assert "중복" in _last(update)


async def test_add_최대개수(repo):
    for i in range(20):
        await repo.add_keyword(100, 100, "include", f"k{i}")
    update = make_message_update("/add 새키워드")
    await hotdeal.cmd_add(update, _ctx(update, repo))
    assert "최대 20개" in _last(update)


# ---- /ban -------------------------------------------------------------------


async def test_ban_제외키워드(repo):
    update = make_message_update("/ban 중고 리퍼")
    await hotdeal.cmd_ban(update, _ctx(update, repo))
    assert "제외 키워드 추가: 중고, 리퍼" in _last(update)
    _, excludes = await repo.list_keywords(100, 100)
    assert excludes == ["중고", "리퍼"]


async def test_ban_최대개수(repo):
    for i in range(10):
        await repo.add_keyword(100, 100, "exclude", f"k{i}")
    update = make_message_update("/ban 새제외")
    await hotdeal.cmd_ban(update, _ctx(update, repo))
    assert "최대 10개" in _last(update)


# ---- /keywords, /del --------------------------------------------------------


async def test_keywords_목록(repo):
    update = make_message_update("/keywords")
    await hotdeal.cmd_keywords(update, _ctx(update, repo))
    assert "전체 수신" in _last(update)

    await repo.add_keyword(100, 100, "include", "아이패드")
    await repo.add_keyword(100, 100, "exclude", "중고")
    update = make_message_update("/keywords")
    await hotdeal.cmd_keywords(update, _ctx(update, repo))
    text = _last(update)
    assert "아이패드" in text
    assert "중고" in text


async def test_del_키워드(repo):
    await repo.add_keyword(100, 100, "include", "아이패드")
    update = make_message_update("/del 아이패드")
    await hotdeal.cmd_del(update, _ctx(update, repo))
    assert "삭제했습니다" in _last(update)

    update = make_message_update("/del 없는키워드")
    await hotdeal.cmd_del(update, _ctx(update, repo))
    assert "없습니다" in _last(update)


# ---- /mode ------------------------------------------------------------------


async def test_mode_조회와_변경(repo):
    update = make_message_update("/mode")
    await hotdeal.cmd_mode(update, _ctx(update, repo))
    assert "실시간" in _last(update)

    update = make_message_update("/mode digest")
    await hotdeal.cmd_mode(update, _ctx(update, repo))
    assert "다이제스트" in _last(update)
    settings = await repo.get_settings(100, 100)
    assert settings.mode == "digest"

    update = make_message_update("/mode 실시간")
    await hotdeal.cmd_mode(update, _ctx(update, repo))
    settings = await repo.get_settings(100, 100)
    assert settings.mode == "realtime"

    update = make_message_update("/mode 이상한값")
    await hotdeal.cmd_mode(update, _ctx(update, repo))
    assert "realtime(실시간)" in _last(update)


# ---- /price -----------------------------------------------------------------


async def test_price_설정과_해제(repo):
    update = make_message_update("/price 1만-5만")
    await hotdeal.cmd_price(update, _ctx(update, repo))
    assert "10,000원 ~ 50,000원" in _last(update)

    settings = await repo.get_settings(100, 100)
    assert settings.min_price == 10_000
    assert settings.max_price == 50_000

    update = make_message_update("/price off")
    await hotdeal.cmd_price(update, _ctx(update, repo))
    assert "해제" in _last(update)
    settings = await repo.get_settings(100, 100)
    assert settings.min_price is None


async def test_price_잘못된_입력(repo):
    update = make_message_update("/price abc")
    await hotdeal.cmd_price(update, _ctx(update, repo))
    assert "인식하지 못했습니다" in _last(update)


# ---- /latest, /settings -----------------------------------------------------


async def test_latest_빈_상태(repo):
    update = make_message_update("/latest")
    await hotdeal.cmd_latest(update, _ctx(update, repo))
    assert "없습니다" in _last(update)


async def test_latest_목록(repo):
    await repo.insert_item(
        make_item("post:1", "아이패드 특가", 500_000), "2026-10-15T00:00:00+00:00"
    )
    await repo.insert_item(make_item("post:2", "에어팟 특가", 200_000), "2026-10-15T00:01:00+00:00")

    update = make_message_update("/latest")
    await hotdeal.cmd_latest(update, _ctx(update, repo))
    texts = _texts(update)
    assert "최신 핫딜 2건" in texts[0]
    assert "에어팟 특가" in texts[1]  # 최신이 먼저
    assert "500,000원" in texts[2]


async def test_settings_요약(repo):
    await repo.add_keyword(100, 100, "include", "아이패드")
    await repo.set_mode(100, 100, "digest")
    await repo.set_price_range(100, 100, 10_000, None)

    update = make_message_update("/settings")
    await hotdeal.cmd_settings(update, _ctx(update, repo))
    text = _last(update)
    assert "다이제스트" in text
    assert "10,000원 이상" in text
    assert "아이패드" in text
