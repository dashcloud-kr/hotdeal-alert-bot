"""RSS 파싱과 핫딜 아이템 모델."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from app.utils.parse import parse_price_from_title

logger = logging.getLogger(__name__)

POST_ID_RE = re.compile(r"[?&]no=(\d+)")


@dataclass(frozen=True)
class HotdealItem:
    guid: str
    source: str
    title: str
    link: str
    description: str
    price: float | None
    published_at: str | None


def extract_guid(link: str) -> str:
    """게시글 고유번호(no=)를 guid로 사용하고, 없으면 링크 전체를 사용한다."""
    match = POST_ID_RE.search(link)
    if match is not None:
        return f"post:{match.group(1)}"
    return f"link:{link}"


def _text(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def _parse_pubdate(raw: str) -> str | None:
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.isoformat()


def parse_rss_items(xml_text: str, source: str) -> list[HotdealItem]:
    """RSS 2.0 XML에서 핫딜 아이템을 추출한다. 형식이 깨진 아이템은 건너뛴다."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("RSS 파싱 실패", exc_info=True)
        return []

    items: list[HotdealItem] = []
    for element in root.iter("item"):
        title = _text(element.find("title"))
        link = _text(element.find("link"))
        if not title or not link:
            continue
        items.append(
            HotdealItem(
                guid=extract_guid(link),
                source=source,
                title=title,
                link=link,
                description=_text(element.find("description")),
                price=parse_price_from_title(title),
                published_at=_parse_pubdate(_text(element.find("pubDate"))),
            )
        )
    return items


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
