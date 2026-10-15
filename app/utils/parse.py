"""사용자 입력 파싱 (제목 가격·가격 범위)."""

from __future__ import annotations

import re

_PRICE_IN_TITLE_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*(만\s*)?원")

_AMOUNT_RE = re.compile(r"^([\d,]+(?:\.\d+)?)\s*(만|천)?$")


def parse_price_from_title(title: str) -> float | None:
    """제목에서 첫 번째 가격을 찾는다. 예: '(7,900원/네멤무료)' → 7900.0"""
    match = _PRICE_IN_TITLE_RE.search(title)
    if match is None:
        return None
    value = float(match.group(1).replace(",", ""))
    if match.group(2):
        value *= 10_000
    return value if value > 0 else None


def _parse_amount(raw: str) -> float | None:
    text = raw.strip().replace(",", "").replace(" ", "")
    if not text:
        return None
    match = _AMOUNT_RE.match(text)
    if match is None:
        return None
    value = float(match.group(1))
    multiplier = {"만": 10_000, "천": 1_000}.get(match.group(2) or "", 1)
    result = value * multiplier
    return result if result > 0 else None


def parse_price_range(raw: str) -> tuple[float | None, float | None] | None:
    """'10000-50000', '1만-5만', '5만-', '-3만' → (min, max).

    유효하지 않으면 None. 양쪽 다 비어 있으면 None.
    """
    text = raw.strip()
    if not text:
        return None
    if text in {"off", "끄기", "해제"}:
        return (None, None)
    if "-" not in text:
        amount = _parse_amount(text)
        if amount is None:
            return None
        return (amount, None)

    left, _, right = text.partition("-")
    min_price = _parse_amount(left) if left.strip() else None
    max_price = _parse_amount(right) if right.strip() else None
    if left.strip() and min_price is None:
        return None
    if right.strip() and max_price is None:
        return None
    if min_price is None and max_price is None:
        return None
    if min_price is not None and max_price is not None and min_price > max_price:
        return None
    return (min_price, max_price)
