"""폴링·다이제스트 잡 테스트."""

from __future__ import annotations

import httpx

from app.handlers import hotdeal
from tests.factories import make_context
from tests.test_repository import make_item

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
<title>뽐뿌게시판</title>
<item>
<title>아이패드 에어 특가 (500,000원/무배)</title>
<link>http://www.ppomppu.co.kr/view.php?id=ppomppu&amp;no=100</link>
<pubDate>Thu, 15 Oct 2026 01:00:00 GMT</pubDate>
</item>
<item>
<title>무선 청소기 (120,000원)</title>
<link>http://www.ppomppu.co.kr/view.php?id=ppomppu&amp;no=101</link>
<pubDate>Thu, 15 Oct 2026 01:01:00 GMT</pubDate>
</item>
</channel>
</rss>"""


class StubRssClient:
    def __init__(self, xml: str = SAMPLE_RSS) -> None:
        self._xml = xml
        self.fetches = 0

    async def fetch(self, url: str) -> str:
        self.fetches += 1
        return self._xml


class FailingRssClient:
    async def fetch(self, url: str) -> str:
        raise httpx.ConnectError("boom")


def _ctx(repo, rss):
    return make_context(bot_data={"repo": repo, "rss": rss})


def _texts(ctx) -> list[str]:
    return [call.kwargs["text"] for call in ctx.bot.send_message.await_args_list]


async def test_부트스트랩_기존글은_알림없이_등록(repo):
    await repo.add_keyword(100, 100, "include", "아이패드")
    ctx = _ctx(repo, StubRssClient())

    await hotdeal.poll_job(ctx)

    assert ctx.bot.send_message.await_count == 0  # 알림 없음
    assert await repo.count_items() == 2
    assert await repo.unprocessed_items() == []  # 전부 처리 표시


async def test_실시간_알림과_필터(repo):
    # 부트스트랩 이후 상황 만들기: 기존 아이템 1건 처리 완료 상태
    await repo.insert_item(make_item("post:0"), "2026-10-15T00:00:00+00:00")
    await repo.mark_processed(["post:0"], "2026-10-15T00:00:00+00:00")

    await repo.add_keyword(100, 100, "include", "아이패드")
    ctx = _ctx(repo, StubRssClient())

    await hotdeal.poll_job(ctx)

    assert ctx.bot.send_message.await_count == 1  # 아이패드만 매칭
    text = _texts(ctx)[0]
    assert "아이패드 에어 특가" in text
    assert "500,000원" in text
    assert "http://www.ppomppu.co.kr/view.php?id=ppomppu&no=100" in text


async def test_중복_알림_없음(repo):
    await repo.insert_item(make_item("post:0"), "2026-10-15T00:00:00+00:00")
    await repo.mark_processed(["post:0"], "2026-10-15T00:00:00+00:00")
    await repo.add_keyword(100, 100, "include", "아이패드")

    ctx = _ctx(repo, StubRssClient())
    await hotdeal.poll_job(ctx)
    assert ctx.bot.send_message.await_count == 1

    await hotdeal.poll_job(ctx)  # 같은 RSS 재수집
    assert ctx.bot.send_message.await_count == 1  # 추가 알림 없음


async def test_다이제스트_모드는_큐에_쌓임(repo):
    await repo.insert_item(make_item("post:0"), "2026-10-15T00:00:00+00:00")
    await repo.mark_processed(["post:0"], "2026-10-15T00:00:00+00:00")
    await repo.set_mode(100, 100, "digest")
    await repo.set_price_range(100, 100, 100_000, 600_000)

    ctx = _ctx(repo, StubRssClient())
    await hotdeal.poll_job(ctx)

    assert ctx.bot.send_message.await_count == 0  # 즉시 발송 없음
    drained = await repo.drain_digest()
    assert {item.guid for _chat, item in drained} == {"post:100", "post:101"}


async def test_다이제스트_잡_발송과_큐_정리(repo):
    await repo.insert_item(
        make_item("post:1", "아이패드 특가", 500_000), "2026-10-15T00:00:00+00:00"
    )
    await repo.insert_item(make_item("post:2", "청소기 특가", 120_000), "2026-10-15T00:01:00+00:00")
    await repo.enqueue_digest(100, "post:1", "2026-10-15T00:02:00+00:00")
    await repo.enqueue_digest(100, "post:2", "2026-10-15T00:02:01+00:00")

    ctx = _ctx(repo, StubRssClient())
    await hotdeal.digest_job(ctx)

    assert ctx.bot.send_message.await_count == 1
    text = _texts(ctx)[0]
    assert "핫딜 다이제스트 (2건)" in text
    assert "아이패드 특가" in text
    assert "500,000원" in text

    assert await repo.drain_digest() == []  # 큐 정리됨


async def test_다이제스트_빈_큐는_발송없음(repo):
    ctx = _ctx(repo, StubRssClient())
    await hotdeal.digest_job(ctx)
    assert ctx.bot.send_message.await_count == 0


async def test_RSS_오류에도_잡은_계속(repo):
    await repo.insert_item(make_item("post:0"), "2026-10-15T00:00:00+00:00")
    await repo.mark_processed(["post:0"], "2026-10-15T00:00:00+00:00")
    await repo.add_keyword(100, 100, "include", "아이패드")

    ctx = _ctx(repo, FailingRssClient())
    await hotdeal.poll_job(ctx)  # 예외가 새어 나오면 실패
    assert ctx.bot.send_message.await_count == 0


async def test_구독자_없으면_수집만(repo):
    await repo.insert_item(make_item("post:0"), "2026-10-15T00:00:00+00:00")
    await repo.mark_processed(["post:0"], "2026-10-15T00:00:00+00:00")

    ctx = _ctx(repo, StubRssClient())
    await hotdeal.poll_job(ctx)

    assert ctx.bot.send_message.await_count == 0
    assert await repo.count_items() == 3  # 기존 1 + 신규 2
    assert await repo.unprocessed_items() == []


async def test_여러_구독자에게_각각_발송(repo):
    await repo.insert_item(make_item("post:0"), "2026-10-15T00:00:00+00:00")
    await repo.mark_processed(["post:0"], "2026-10-15T00:00:00+00:00")

    await repo.add_keyword(1, 100, "include", "아이패드")
    await repo.add_keyword(2, 200, "include", "청소기")

    ctx = _ctx(repo, StubRssClient())
    await hotdeal.poll_job(ctx)

    assert ctx.bot.send_message.await_count == 2
    chat_ids = {call.kwargs["chat_id"] for call in ctx.bot.send_message.await_args_list}
    assert chat_ids == {100, 200}
