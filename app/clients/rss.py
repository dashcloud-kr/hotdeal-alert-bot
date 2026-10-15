"""RSS 피드 HTTP 클라이언트."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; dashcloud-hotdeal-bot/1.0)"


class RssClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def fetch(self, url: str) -> str:
        """RSS XML 원문을 가져온다. HTTP 오류는 예외로 전파."""
        response = await self._http.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        return response.text
