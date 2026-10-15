"""키워드·가격 필터 매칭 테스트."""

from __future__ import annotations

from app.services.matching import Filters, matches
from app.services.rss import HotdealItem


def item(title: str, price: float | None = None) -> HotdealItem:
    return HotdealItem(
        guid="post:1",
        source="뽐뿌",
        title=title,
        link="http://x.com/1",
        description="",
        price=price,
        published_at=None,
    )


def test_필터_없으면_전부_통과():
    assert matches(item("아무거나"), Filters()) is True


def test_포함_키워드_매칭():
    filters = Filters(includes=["아이패드"])
    assert matches(item("아이패드 에어 5세대 특가"), filters) is True
    assert matches(item("에어팟 프로"), filters) is False


def test_포함_키워드_대소문자_무시():
    filters = Filters(includes=["iPad"])
    assert matches(item("apple IPAD air"), filters) is True


def test_제외_키워드():
    filters = Filters(excludes=["중고", "리퍼"])
    assert matches(item("아이패드 중고급"), filters) is False
    assert matches(item("아이패드 새제품"), filters) is True


def test_제외가_포함보다_우선():
    filters = Filters(includes=["아이패드"], excludes=["중고"])
    assert matches(item("아이패드 중고"), filters) is False


def test_가격_최소():
    filters = Filters(min_price=10_000)
    assert matches(item("A", price=15_000), filters) is True
    assert matches(item("A", price=5_000), filters) is False
    assert matches(item("A", price=None), filters) is False  # 가격 미상은 제외


def test_가격_최대():
    filters = Filters(max_price=50_000)
    assert matches(item("A", price=30_000), filters) is True
    assert matches(item("A", price=80_000), filters) is False


def test_가격_범위():
    filters = Filters(min_price=10_000, max_price=50_000)
    assert matches(item("A", price=30_000), filters) is True
    assert matches(item("A", price=9_999), filters) is False
    assert matches(item("A", price=50_001), filters) is False


def test_복합_필터():
    filters = Filters(includes=["노트북"], excludes=["게이밍"], min_price=500_000)
    assert matches(item("맥북 에어 노트북", price=1_200_000), filters) is True
    assert matches(item("게이밍 노트북", price=1_200_000), filters) is False
    assert matches(item("노트북 파우치", price=20_000), filters) is False
