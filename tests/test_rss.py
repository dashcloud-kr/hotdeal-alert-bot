"""RSS 파싱 테스트."""

from __future__ import annotations

from app.services.rss import extract_guid, parse_rss_items

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8" ?>
<rss xmlns:dc="http://purl.org/dc/elements/1.1/" version="2.0">
<channel>
<title>뽐뿌게시판</title>
<link>http://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu</link>
<item>
<title>[네이버] 포크밸리 한돈 뒷다리살 (7,900원/네멤무료)</title>
<link>http://www.ppomppu.co.kr/zboard/view.php?id=ppomppu&amp;no=740322</link>
<description>가격 괜찮아요</description>
<author>삼복이2</author>
<pubDate>Thu, 15 Oct 2026 01:09:31 GMT</pubDate>
<hits> [0|27|0|0]</hits>
</item>
<item>
<title>가격 없는 글</title>
<link>http://www.ppomppu.co.kr/zboard/view.php?id=ppomppu&amp;no=740321</link>
<pubDate>invalid-date</pubDate>
</item>
<item>
<title></title>
<link>http://www.ppomppu.co.kr/zboard/view.php?id=ppomppu&amp;no=740320</link>
</item>
</channel>
</rss>"""


def test_아이템_파싱():
    items = parse_rss_items(SAMPLE_RSS, "뽐뿌")
    assert len(items) == 2  # 제목 없는 아이템은 제외

    first = items[0]
    assert first.guid == "post:740322"
    assert first.title == "[네이버] 포크밸리 한돈 뒷다리살 (7,900원/네멤무료)"
    assert first.link == "http://www.ppomppu.co.kr/zboard/view.php?id=ppomppu&no=740322"
    assert first.price == 7900
    assert first.source == "뽐뿌"
    assert first.published_at is not None
    assert first.published_at.startswith("2026-10-15")


def test_가격과_날짜_없는_아이템():
    items = parse_rss_items(SAMPLE_RSS, "뽐뿌")
    second = items[1]
    assert second.price is None
    assert second.published_at is None
    assert second.guid == "post:740321"


def test_깨진_XML은_빈_목록():
    assert parse_rss_items("<rss><channel><item>", "뽐뿌") == []
    assert parse_rss_items("", "뽐뿌") == []


def test_guid_추출():
    assert extract_guid("http://x.com/view.php?id=ppomppu&no=123") == "post:123"
    assert extract_guid("http://x.com/view.php?no=9") == "post:9"
    assert extract_guid("http://x.com/page") == "link:http://x.com/page"
