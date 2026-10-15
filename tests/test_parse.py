"""제목 가격·가격 범위 파싱 테스트."""

from __future__ import annotations

from app.utils.parse import parse_price_from_title, parse_price_range


def test_제목_가격_콤마():
    assert parse_price_from_title("(7,900원/네멤무료)") == 7900


def test_제목_가격_원_포함():
    assert parse_price_from_title("삼성 TV 1,234,000원 무료배송") == 1_234_000


def test_제목_가격_만원():
    assert parse_price_from_title("1.5만원 특가") == 15_000


def test_제목_첫_가격만():
    assert parse_price_from_title("A 1,000원 B 2,000원") == 1000


def test_제목_가격_없으면_None():
    assert parse_price_from_title("무료 나눔") is None
    assert parse_price_from_title("가격 미정") is None


def test_가격범위_일반():
    assert parse_price_range("10000-50000") == (10_000, 50_000)


def test_가격범위_만원():
    assert parse_price_range("1만-5만") == (10_000, 50_000)


def test_가격범위_한쪽만():
    assert parse_price_range("5만-") == (50_000, None)
    assert parse_price_range("-3만") == (None, 30_000)


def test_가격범위_단일값():
    assert parse_price_range("10000") == (10_000, None)


def test_가격범위_해제():
    assert parse_price_range("off") == (None, None)
    assert parse_price_range("해제") == (None, None)


def test_가격범위_잘못된_입력():
    assert parse_price_range("") is None
    assert parse_price_range("abc") is None
    assert parse_price_range("5만-1만") is None  # min > max
    assert parse_price_range("오만원-") is None
