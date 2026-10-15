"""메시지 포맷 유틸."""

from __future__ import annotations

from app.services.rss import HotdealItem
from app.utils.text import chunk_text


def format_krw(value: float) -> str:
    return f"{value:,.0f}원"


def format_price_range(min_price: float | None, max_price: float | None) -> str:
    if min_price is None and max_price is None:
        return "가격 제한 없음"
    if min_price is not None and max_price is not None:
        return f"{format_krw(min_price)} ~ {format_krw(max_price)}"
    if min_price is not None:
        return f"{format_krw(min_price)} 이상"
    return f"{format_krw(max_price)} 이하"  # type: ignore[arg-type]


def format_item_message(item: HotdealItem) -> str:
    lines = [f"[{item.source}] {item.title}"]
    if item.price is not None:
        lines.append(format_krw(item.price))
    lines.append(item.link)
    return "\n".join(lines)


def format_digest_messages(items: list[HotdealItem]) -> list[str]:
    lines = [f"핫딜 다이제스트 ({len(items)}건)"]
    for index, item in enumerate(items, start=1):
        price = f" · {format_krw(item.price)}" if item.price is not None else ""
        lines.append(f"{index}. {item.title}{price}")
        lines.append(item.link)
    return chunk_text("\n".join(lines))
