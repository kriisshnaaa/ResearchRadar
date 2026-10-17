"""Small transactional SQLite repository."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from ..models import Record, SourceStatus, utc_now


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path))
        self.connection.row_factory = sqlite3.Row
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        self.connection.executescript(schema)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def start_run(self, topic: str) -> int:
        cur = self.connection.execute(
            "INSERT INTO runs(topic, started_at, status) VALUES (?, ?, ?)",
            (topic, utc_now(), "running"),
        )
        self.connection.commit()
        return int(cur.lastrowid)

    def upsert_items(self, items: Iterable[Record]) -> None:
        now = utc_now()
        with self.connection:
            for item in items:
                self.connection.execute(
                    """INSERT INTO items(id,title,url,source_type,source_name,published_at,
                       content_hash,first_seen_at,last_seen_at,last_topic)
                       VALUES (?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET last_seen_at=excluded.last_seen_at,
                       last_topic=excluded.last_topic, published_at=COALESCE(excluded.published_at, items.published_at)""",
                    (item.id, item.title, item.url, item.source_type, item.source_name,
                     item.published_at, item.content_hash, now, now, item.topic),
                )

    def seen_ids(self, items: Iterable[Record]) -> set[str]:
        ids = [item.id for item in items]
        if not ids:
            return set()
        placeholders = ",".join("?" for _ in ids)
        rows = self.connection.execute(
            f"""SELECT DISTINCT ri.item_id AS id FROM run_items ri
                JOIN runs r ON r.id = ri.run_id
                WHERE r.status='delivered' AND ri.item_id IN ({placeholders})""", ids
        ).fetchall()
        return {str(row["id"]) for row in rows}

    def save_run_items(self, run_id: int, items: Iterable[Record], included: bool = True) -> None:
        with self.connection:
            for item in items:
                self.connection.execute(
                    "INSERT OR REPLACE INTO run_items(run_id,item_id,duplicate_cluster_id,included_in_digest) VALUES (?,?,?,?)",
                    (run_id, item.id, item.duplicate_cluster_id, int(included)),
                )

    def save_source_statuses(self, run_id: int, statuses: Iterable[SourceStatus]) -> None:
        with self.connection:
            for status in statuses:
                self.connection.execute(
                    """INSERT OR REPLACE INTO source_statuses
                    (run_id,source_type,source_name,attempted,success,item_count,error)
                    VALUES (?,?,?,?,?,?,?)""",
                    (run_id, status.source_type, status.source_name, int(status.attempted),
                     int(status.success), status.item_count, status.error),
                )

    def set_delivery(self, run_id: int, status: str, parts_sent: int = 0, error: Optional[str] = None) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO deliveries(run_id,status,parts_sent,error) VALUES (?,?,?,?)",
                (run_id, status, parts_sent, error),
            )
            self.connection.execute("UPDATE runs SET delivery_status=? WHERE id=?", (status, run_id))

    def finish_run(self, run_id: int, status: str, item_count: int, error_summary: Optional[str] = None) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE runs SET finished_at=?,status=?,item_count=?,error_summary=? WHERE id=?",
                (utc_now(), status, item_count, error_summary, run_id),
            )

    def get_run(self, run_id: int) -> sqlite3.Row:
        row = self.connection.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return row
