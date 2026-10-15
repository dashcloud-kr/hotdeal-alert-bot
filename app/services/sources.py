"""핫딜 소스 정의."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeedSource:
    key: str
    name: str
    url: str


PPOMPPU = FeedSource(
    key="ppomppu",
    name="뽐뿌",
    url="https://www.ppomppu.co.kr/rss.php?id=ppomppu",
)

SOURCES: list[FeedSource] = [PPOMPPU]
