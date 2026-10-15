"""SQLite 저장소 (아이템·키워드·설정·다이제스트 큐)."""

from __future__ import annotations

from dataclasses import dataclass

from app.db import Database
from app.services.matching import Filters
from app.services.rss import HotdealItem

ITEM_COLUMNS = "guid, source, title, link, description, price, published_at"


@dataclass(frozen=True)
class Settings:
    mode: str
    min_price: float | None
    max_price: float | None


def _row_to_item(row) -> HotdealItem:
    return HotdealItem(
        guid=str(row["guid"]),
        source=str(row["source"]),
        title=str(row["title"]),
        link=str(row["link"]),
        description=str(row["description"] or ""),
        price=float(row["price"]) if row["price"] is not None else None,
        published_at=str(row["published_at"]) if row["published_at"] is not None else None,
    )


class Repository:
    def __init__(self, db: Database) -> None:
        self._db = db

    # ---- 아이템 -----------------------------------------------------------

    async def insert_item(self, item: HotdealItem, fetched_at: str) -> bool:
        """새 아이템이면 True. 이미 있는 guid면 False."""
        affected = await self._db.execute_affected(
            f"INSERT OR IGNORE INTO items ({ITEM_COLUMNS}, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item.guid,
                item.source,
                item.title,
                item.link,
                item.description,
                item.price,
                item.published_at,
                fetched_at,
            ),
        )
        return affected > 0

    async def count_items(self) -> int:
        row = await self._db.fetchone("SELECT COUNT(*) AS count FROM items")
        return int(row["count"]) if row is not None else 0

    async def unprocessed_items(self, limit: int = 200) -> list[HotdealItem]:
        rows = await self._db.fetchall(
            f"SELECT {ITEM_COLUMNS} FROM items WHERE processed_at IS NULL "
            "ORDER BY fetched_at, rowid LIMIT ?",
            (limit,),
        )
        return [_row_to_item(row) for row in rows]

    async def mark_processed(self, guids: list[str], at_iso: str) -> None:
        for guid in guids:
            await self._db.execute(
                "UPDATE items SET processed_at = ? WHERE guid = ?", (at_iso, guid)
            )

    async def recent_items(self, limit: int = 5) -> list[HotdealItem]:
        rows = await self._db.fetchall(
            f"SELECT {ITEM_COLUMNS} FROM items ORDER BY rowid DESC LIMIT ?",
            (limit,),
        )
        return [_row_to_item(row) for row in rows]

    # ---- 키워드 -----------------------------------------------------------

    async def add_keyword(self, user_id: int, chat_id: int, kind: str, keyword: str) -> bool:
        affected = await self._db.execute_affected(
            "INSERT OR IGNORE INTO keywords (user_id, chat_id, kind, keyword) VALUES (?, ?, ?, ?)",
            (user_id, chat_id, kind, keyword),
        )
        return affected > 0

    async def remove_keyword(self, user_id: int, chat_id: int, keyword: str) -> bool:
        affected = await self._db.execute_affected(
            "DELETE FROM keywords WHERE user_id = ? AND chat_id = ? AND keyword = ?",
            (user_id, chat_id, keyword),
        )
        return affected > 0

    async def list_keywords(self, user_id: int, chat_id: int) -> tuple[list[str], list[str]]:
        rows = await self._db.fetchall(
            "SELECT kind, keyword FROM keywords WHERE user_id = ? AND chat_id = ? ORDER BY id",
            (user_id, chat_id),
        )
        includes = [str(row["keyword"]) for row in rows if row["kind"] == "include"]
        excludes = [str(row["keyword"]) for row in rows if row["kind"] == "exclude"]
        return includes, excludes

    # ---- 설정 -------------------------------------------------------------

    async def get_settings(self, user_id: int, chat_id: int) -> Settings:
        row = await self._db.fetchone(
            "SELECT mode, min_price, max_price FROM settings WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id),
        )
        if row is None:
            return Settings(mode="realtime", min_price=None, max_price=None)
        return Settings(
            mode=str(row["mode"]),
            min_price=float(row["min_price"]) if row["min_price"] is not None else None,
            max_price=float(row["max_price"]) if row["max_price"] is not None else None,
        )

    async def set_mode(self, user_id: int, chat_id: int, mode: str) -> None:
        await self._db.execute(
            "INSERT INTO settings (user_id, chat_id, mode) VALUES (?, ?, ?) "
            "ON CONFLICT (user_id, chat_id) DO UPDATE SET mode = excluded.mode",
            (user_id, chat_id, mode),
        )

    async def set_price_range(
        self, user_id: int, chat_id: int, min_price: float | None, max_price: float | None
    ) -> None:
        await self._db.execute(
            "INSERT INTO settings (user_id, chat_id, min_price, max_price) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (user_id, chat_id) DO UPDATE SET "
            "min_price = excluded.min_price, max_price = excluded.max_price",
            (user_id, chat_id, min_price, max_price),
        )

    async def all_subscribers(self) -> list[tuple[int, int]]:
        rows = await self._db.fetchall(
            "SELECT DISTINCT user_id, chat_id FROM keywords "
            "UNION SELECT user_id, chat_id FROM settings"
        )
        return [(int(row["user_id"]), int(row["chat_id"])) for row in rows]

    async def filters_for(self, user_id: int, chat_id: int) -> Filters:
        includes, excludes = await self.list_keywords(user_id, chat_id)
        settings = await self.get_settings(user_id, chat_id)
        return Filters(
            includes=includes,
            excludes=excludes,
            min_price=settings.min_price,
            max_price=settings.max_price,
        )

    # ---- 다이제스트 큐 ----------------------------------------------------

    async def enqueue_digest(self, chat_id: int, guid: str, queued_at: str) -> None:
        await self._db.execute(
            "INSERT OR IGNORE INTO digest_queue (chat_id, guid, queued_at) VALUES (?, ?, ?)",
            (chat_id, guid, queued_at),
        )

    async def drain_digest(self, limit: int = 200) -> list[tuple[int, HotdealItem]]:
        rows = await self._db.fetchall(
            f"SELECT dq.chat_id AS chat_id, i.{ITEM_COLUMNS.replace(', ', ', i.')} "
            "FROM digest_queue dq JOIN items i ON i.guid = dq.guid "
            "ORDER BY dq.queued_at LIMIT ?",
            (limit,),
        )
        return [(int(row["chat_id"]), _row_to_item(row)) for row in rows]

    async def clear_digest(self, chat_id: int, guids: list[str]) -> None:
        for guid in guids:
            await self._db.execute(
                "DELETE FROM digest_queue WHERE chat_id = ? AND guid = ?", (chat_id, guid)
            )
