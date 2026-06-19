import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

from fatsecret_telegram_bridge.models import AliasRecord


class Store:
    def __init__(self, path: str):
        # The bot runs queries from worker threads (asyncio.to_thread), so the
        # connection must be usable outside its creating thread. check_same_thread
        # lifts that restriction, and _lock serializes access (a single Connection
        # cannot be used concurrently from multiple threads).
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._migrate()

    def _migrate(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS aliases (
                alias             TEXT PRIMARY KEY,
                food_id           TEXT NOT NULL,
                serving_id        TEXT NOT NULL,
                grams_per_serving REAL NOT NULL,
                food_name         TEXT NOT NULL,
                created_at        TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        TEXT NOT NULL,
                raw_text  TEXT NOT NULL,
                entry_ids TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def get_alias(self, alias: str) -> Optional[AliasRecord]:
        with self._lock:
            row = self.conn.execute(
                "SELECT alias, food_id, serving_id, grams_per_serving, food_name "
                "FROM aliases WHERE alias = ?",
                (alias,),
            ).fetchone()
        if row is None:
            return None
        return AliasRecord(
            alias=row["alias"], food_id=row["food_id"],
            serving_id=row["serving_id"],
            grams_per_serving=row["grams_per_serving"],
            food_name=row["food_name"],
        )

    def save_alias(self, rec: AliasRecord) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO aliases "
                "(alias, food_id, serving_id, grams_per_serving, food_name, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(alias) DO UPDATE SET "
                "food_id=excluded.food_id, serving_id=excluded.serving_id, "
                "grams_per_serving=excluded.grams_per_serving, "
                "food_name=excluded.food_name",
                (rec.alias, rec.food_id, rec.serving_id, rec.grams_per_serving,
                 rec.food_name, datetime.now(timezone.utc).isoformat()),
            )
            self.conn.commit()

    def all_alias_names(self) -> list[str]:
        with self._lock:
            rows = self.conn.execute("SELECT alias FROM aliases").fetchall()
        return [r["alias"] for r in rows]

    def add_log(self, raw_text: str, entry_ids: list[str]) -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO log (ts, raw_text, entry_ids) VALUES (?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), raw_text,
                 json.dumps(entry_ids)),
            )
            self.conn.commit()
            return int(cur.lastrowid)

    def get_log(self, log_id: int) -> Optional[dict]:
        with self._lock:
            row = self.conn.execute(
                "SELECT id, ts, raw_text, entry_ids FROM log WHERE id = ?",
                (log_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"], "ts": row["ts"], "raw_text": row["raw_text"],
            "entry_ids": json.loads(row["entry_ids"]),
        }
