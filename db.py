import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
from pathlib import Path
from typing import Iterator

DB_PATH = Path(__file__).parent / "data" / "trending.db"


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS trending_items (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                platform      TEXT    NOT NULL,
                region        TEXT    NOT NULL DEFAULT 'cn',
                rank          INTEGER NOT NULL,
                title         TEXT    NOT NULL,
                url           TEXT,
                hot_value     TEXT,
                cover         TEXT,
                snapshot_date TEXT    NOT NULL,
                fetched_at    TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_region_platform_date
                ON trending_items (region, platform, snapshot_date);

            CREATE TABLE IF NOT EXISTS scrape_runs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                platform      TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                started_at    TEXT NOT NULL,
                finished_at   TEXT,
                status        TEXT NOT NULL,
                item_count    INTEGER DEFAULT 0,
                error         TEXT
            );
            """
        )


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_items(platform: str, items: list[dict], region: str = "cn", snapshot_date: str | None = None) -> int:
    snapshot_date = snapshot_date or date.today().isoformat()
    fetched_at = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM trending_items WHERE platform = ? AND snapshot_date = ?",
            (platform, snapshot_date),
        )
        conn.executemany(
            """
            INSERT INTO trending_items
                (platform, region, rank, title, url, hot_value, cover, snapshot_date, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    platform,
                    region,
                    item.get("rank", i + 1),
                    item["title"],
                    item.get("url"),
                    item.get("hot_value"),
                    item.get("cover"),
                    snapshot_date,
                    fetched_at,
                )
                for i, item in enumerate(items)
            ],
        )
    return len(items)


def get_latest(platform: str) -> list[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(snapshot_date) AS d FROM trending_items WHERE platform = ?",
            (platform,),
        ).fetchone()
        if not row or not row["d"]:
            return []
        snapshot_date = row["d"]
        rows = conn.execute(
            """
            SELECT rank, title, url, hot_value, cover, snapshot_date, fetched_at, region
            FROM trending_items
            WHERE platform = ? AND snapshot_date = ?
            ORDER BY rank ASC
            """,
            (platform, snapshot_date),
        ).fetchall()
        return [dict(r) for r in rows]


def get_history_dates(platform: str, limit: int = 30) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT snapshot_date FROM trending_items
            WHERE platform = ?
            ORDER BY snapshot_date DESC
            LIMIT ?
            """,
            (platform, limit),
        ).fetchall()
        return [r["snapshot_date"] for r in rows]


def get_by_date(platform: str, snapshot_date: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT rank, title, url, hot_value, cover, snapshot_date, fetched_at, region
            FROM trending_items
            WHERE platform = ? AND snapshot_date = ?
            ORDER BY rank ASC
            """,
            (platform, snapshot_date),
        ).fetchall()
        return [dict(r) for r in rows]


def all_snapshot_dates(limit: int = 30) -> list[str]:
    """Distinct snapshot dates across all platforms, most recent first."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT snapshot_date FROM trending_items ORDER BY snapshot_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [r["snapshot_date"] for r in rows]


def get_by_region(region: str, snapshot_date: str) -> list[dict]:
    """Return all items for a (region, snapshot_date) across all platforms in that region."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT platform, rank, title, url, hot_value, cover, snapshot_date, fetched_at, region
            FROM trending_items
            WHERE region = ? AND snapshot_date = ?
            ORDER BY platform, rank ASC
            """,
            (region, snapshot_date),
        ).fetchall()
        return [dict(r) for r in rows]


def log_run_start(platform: str) -> int:
    snapshot_date = date.today().isoformat()
    started_at = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO scrape_runs (platform, snapshot_date, started_at, status)
            VALUES (?, ?, ?, 'running')
            """,
            (platform, snapshot_date, started_at),
        )
        return cur.lastrowid


def log_run_finish(run_id: int, status: str, item_count: int = 0, error: str | None = None) -> None:
    finished_at = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE scrape_runs
            SET finished_at = ?, status = ?, item_count = ?, error = ?
            WHERE id = ?
            """,
            (finished_at, status, item_count, error, run_id),
        )


def get_runs_by_platform(platform: str, limit: int = 20) -> list[dict]:
    """Most recent scrape runs for one platform, newest first."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT snapshot_date, started_at, finished_at, status, item_count, error
            FROM scrape_runs
            WHERE platform = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (platform, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_recent_runs(limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT platform, snapshot_date, started_at, finished_at, status, item_count, error
            FROM scrape_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
