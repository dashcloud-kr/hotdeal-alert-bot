"""키워드·가격 필터 매칭 (순수 함수)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.rss import HotdealItem


@dataclass(frozen=True)
class Filters:
    includes: list[str] = field(default_factory=list)
    excludes: list[str] = field(default_factory=list)
    min_price: float | None = None
    max_price: float | None = None


def matches(item: HotdealItem, filters: Filters) -> bool:
    """제외 키워드 → 포함 키워드 → 가격 범위 순으로 판정한다.

    - 제외 키워드에 걸리면 무조건 제외
    - 포함 키워드가 없으면 전부 통과, 있으면 하나라도 포함되어야 통과
    - 가격 필터가 있는데 가격을 알 수 없으면 제외
    """
    title = item.title.lower()

    for keyword in filters.excludes:
        if keyword.lower() in title:
            return False

    includes = filters.includes
    if includes and not any(keyword.lower() in title for keyword in includes):
        return False

    if filters.min_price is not None and (
        item.price is None or item.price < filters.min_price
    ):
        return False

    max_exceeded = filters.max_price is not None and (
        item.price is None or item.price > filters.max_price
    )
    return not max_exceeded
