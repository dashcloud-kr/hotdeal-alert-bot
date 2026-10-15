"""Repository (SQLite) 테스트."""

from __future__ import annotations

from app.services.rss import HotdealItem


def make_item(
    guid: str = "post:1", title: str = "테스트 핫딜", price: float | None = 1000
) -> HotdealItem:
    return HotdealItem(
        guid=guid,
        source="뽐뿌",
        title=title,
        link=f"http://x.com/view.php?no={guid}",
        description="설명",
        price=price,
        published_at="2026-10-15T01:00:00+00:00",
    )


async def test_아이템_삽입_중복_판별(repo):
    assert await repo.insert_item(make_item("post:1"), "2026-10-15T00:00:00+00:00") is True
    assert await repo.insert_item(make_item("post:1"), "2026-10-15T00:01:00+00:00") is False
    assert await repo.count_items() == 1


async def test_미처리_아이템_조회와_처리_표시(repo):
    await repo.insert_item(make_item("post:1"), "2026-10-15T00:00:00+00:00")
    await repo.insert_item(make_item("post:2"), "2026-10-15T00:01:00+00:00")

    unprocessed = await repo.unprocessed_items()
    assert [i.guid for i in unprocessed] == ["post:1", "post:2"]

    await repo.mark_processed(["post:1"], "2026-10-15T00:02:00+00:00")
    unprocessed = await repo.unprocessed_items()
    assert [i.guid for i in unprocessed] == ["post:2"]


async def test_최근_아이템_역순(repo):
    await repo.insert_item(make_item("post:1"), "2026-10-15T00:00:00+00:00")
    await repo.insert_item(make_item("post:2"), "2026-10-15T00:01:00+00:00")
    recent = await repo.recent_items(5)
    assert [i.guid for i in recent] == ["post:2", "post:1"]


async def test_키워드_추가_중복_목록_삭제(repo):
    assert await repo.add_keyword(1, 100, "include", "아이패드") is True
    assert await repo.add_keyword(1, 100, "include", "아이패드") is False
    assert await repo.add_keyword(1, 100, "exclude", "중고") is True

    includes, excludes = await repo.list_keywords(1, 100)
    assert includes == ["아이패드"]
    assert excludes == ["중고"]

    assert await repo.remove_keyword(1, 100, "아이패드") is True
    assert await repo.remove_keyword(1, 100, "아이패드") is False
    includes, _ = await repo.list_keywords(1, 100)
    assert includes == []


async def test_키워드는_채팅별_분리(repo):
    await repo.add_keyword(1, 100, "include", "A")
    await repo.add_keyword(1, 200, "include", "B")
    assert await repo.list_keywords(1, 100) == (["A"], [])
    assert await repo.list_keywords(1, 200) == (["B"], [])


async def test_설정_기본값과_변경(repo):
    settings = await repo.get_settings(1, 100)
    assert settings.mode == "realtime"
    assert settings.min_price is None

    await repo.set_mode(1, 100, "digest")
    await repo.set_price_range(1, 100, 10_000, 50_000)
    settings = await repo.get_settings(1, 100)
    assert settings.mode == "digest"
    assert settings.min_price == 10_000
    assert settings.max_price == 50_000

    await repo.set_price_range(1, 100, None, None)
    settings = await repo.get_settings(1, 100)
    assert settings.min_price is None
    assert settings.max_price is None


async def test_구독자_목록_키워드와_설정_합집합(repo):
    await repo.add_keyword(1, 100, "include", "A")
    await repo.set_mode(2, 200, "digest")
    await repo.add_keyword(1, 100, "include", "B")  # 같은 채팅 중복

    subscribers = sorted(await repo.all_subscribers())
    assert subscribers == [(1, 100), (2, 200)]


async def test_필터_조합(repo):
    await repo.add_keyword(1, 100, "include", "노트북")
    await repo.add_keyword(1, 100, "exclude", "게이밍")
    await repo.set_price_range(1, 100, 500_000, None)

    filters = await repo.filters_for(1, 100)
    assert filters.includes == ["노트북"]
    assert filters.excludes == ["게이밍"]
    assert filters.min_price == 500_000
    assert filters.max_price is None


async def test_다이제스트_큐_추가_드레인_삭제(repo):
    await repo.insert_item(make_item("post:1"), "2026-10-15T00:00:00+00:00")
    await repo.enqueue_digest(100, "post:1", "2026-10-15T00:01:00+00:00")
    await repo.enqueue_digest(100, "post:1", "2026-10-15T00:02:00+00:00")  # 중복 무시

    drained = await repo.drain_digest()
    assert len(drained) == 1
    chat_id, item = drained[0]
    assert chat_id == 100
    assert item.guid == "post:1"
    assert item.title == "테스트 핫딜"
    assert item.price == 1000

    await repo.clear_digest(100, ["post:1"])
    assert await repo.drain_digest() == []


async def test_마이그레이션_재적용_안전(tmp_path):
    from app.db import Database
    from app.services.repository import Repository
    from bot import MIGRATIONS

    path = tmp_path / "again.db"
    first = Database(path)
    await first.connect(MIGRATIONS)
    await Repository(first).add_keyword(1, 100, "include", "A")
    await first.close()

    second = Database(path)
    await second.connect(MIGRATIONS)
    try:
        includes, _ = await Repository(second).list_keywords(1, 100)
        assert includes == ["A"]
    finally:
        await second.close()
