import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "pc_builder.db"


def get_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        brand TEXT NOT NULL,
        name TEXT NOT NULL,
        model TEXT NOT NULL,
        specs TEXT NOT NULL DEFAULT '{}',
        tdp INTEGER DEFAULT 0,
        benchmark_score INTEGER DEFAULT 0,
        reference_price INTEGER DEFAULT 0,
        release_year INTEGER,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS builds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        purpose TEXT DEFAULT 'balanced',
        budget INTEGER DEFAULT 0,
        notes TEXT DEFAULT '',
        share_token TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS build_parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        build_id INTEGER NOT NULL,
        part_id INTEGER NOT NULL,
        quantity INTEGER DEFAULT 1,
        custom_price INTEGER,
        is_used INTEGER DEFAULT 0,
        FOREIGN KEY (build_id) REFERENCES builds(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id)
    );

    CREATE TABLE IF NOT EXISTS price_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_id INTEGER NOT NULL,
        source TEXT NOT NULL,
        price INTEGER NOT NULL,
        url TEXT,
        title TEXT,
        is_used INTEGER DEFAULT 0,
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
        price INTEGER NOT NULL,
        source TEXT NOT NULL,
        recorded_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sync_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        started_at TEXT,
        completed_at TEXT,
        added INTEGER DEFAULT 0,
        skipped INTEGER DEFAULT 0,
        error TEXT,
        trigger TEXT DEFAULT 'manual'
    );
    """)

    conn.commit()

    # マイグレーション: 既存DBに新カラムを追加
    _migrate(conn)

    # seed initial data if parts table is empty
    row = c.execute("SELECT COUNT(*) FROM parts").fetchone()
    if row[0] == 0:
        _seed_initial_data(conn)

    conn.close()


def _migrate(conn):
    """既存DBへの後方互換マイグレーション"""
    c = conn.cursor()
    existing = {row[1] for row in c.execute("PRAGMA table_info(builds)").fetchall()}
    if "notes" not in existing:
        c.execute("ALTER TABLE builds ADD COLUMN notes TEXT DEFAULT ''")
    if "share_token" not in existing:
        # SQLiteはUNIQUE付きALTER TABLE不可 → カラム追加後にインデックスを作成
        c.execute("ALTER TABLE builds ADD COLUMN share_token TEXT")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_builds_share_token ON builds(share_token) WHERE share_token IS NOT NULL")
    conn.commit()


def _seed_initial_data(conn):
    data_path = Path(__file__).parent / "data" / "initial_parts.json"
    if not data_path.exists():
        return
    with open(data_path, encoding="utf-8") as f:
        parts = json.load(f)
    c = conn.cursor()
    for p in parts:
        c.execute(
            """INSERT INTO parts (category, brand, name, model, specs, tdp, benchmark_score, reference_price, release_year, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                p["category"], p["brand"], p["name"], p["model"],
                json.dumps(p.get("specs", {}), ensure_ascii=False),
                p.get("tdp", 0), p.get("benchmark_score", 0),
                p.get("reference_price", 0), p.get("release_year"),
                p.get("notes", ""),
            ),
        )
    conn.commit()
