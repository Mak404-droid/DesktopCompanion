import sqlite3
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "companion.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def initialize_database():
    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        columns = [
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(memories)"
            ).fetchall()
        ]

        # Upgrade old database
        if "category" not in columns:

            conn.execute(
                "ALTER TABLE memories "
                "ADD COLUMN category TEXT DEFAULT 'general'"
            )

        if "updated_at" not in columns:

            conn.execute(
                "ALTER TABLE memories "
                "ADD COLUMN updated_at TEXT"
            )

            conn.execute(
                "UPDATE memories "
                "SET updated_at = created_at "
                "WHERE updated_at IS NULL"
            )

        conn.commit()


def save_memory(memory, category="general"):

    if not memory or not memory.strip():
        return None

    memory = memory.strip()
    category = category.strip().lower()

    now = datetime.now().isoformat()

    with get_connection() as conn:

        existing = conn.execute(
            """
            SELECT id
            FROM memories
            WHERE LOWER(TRIM(memory)) = LOWER(TRIM(?))
            """,
            (memory,)
        ).fetchone()

        if existing:
            return existing[0]

        cursor = conn.execute(
            """
            INSERT INTO memories
            (memory, category, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                memory,
                category,
                now,
                now
            )
        )

        conn.commit()

        return cursor.lastrowid


def update_memory(
    memory_id,
    memory,
    category=None
):

    if not memory or not memory.strip():
        return False

    now = datetime.now().isoformat()

    with get_connection() as conn:

        if category:

            conn.execute(
                """
                UPDATE memories
                SET memory = ?,
                    category = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    memory.strip(),
                    category.strip().lower(),
                    now,
                    memory_id
                )
            )

        else:

            conn.execute(
                """
                UPDATE memories
                SET memory = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    memory.strip(),
                    now,
                    memory_id
                )
            )

        conn.commit()

        return True


def get_memories():

    with get_connection() as conn:

        return conn.execute(
            """
            SELECT
                id,
                memory,
                category,
                created_at,
                updated_at
            FROM memories
            ORDER BY id ASC
            """
        ).fetchall()


def get_memories_by_category(category):

    with get_connection() as conn:

        return conn.execute(
            """
            SELECT
                id,
                memory,
                category,
                created_at,
                updated_at
            FROM memories
            WHERE category = ?
            ORDER BY id ASC
            """,
            (category.lower(),)
        ).fetchall()


def search_memories(keyword):

    keyword = keyword.strip()

    if not keyword:
        return []

    with get_connection() as conn:

        return conn.execute(
            """
            SELECT
                id,
                memory,
                category,
                created_at,
                updated_at
            FROM memories
            WHERE memory LIKE ?
            ORDER BY id ASC
            """,
            (f"%{keyword}%",)
        ).fetchall()


def delete_memory(memory_id):

    with get_connection() as conn:

        cursor = conn.execute(
            """
            DELETE FROM memories
            WHERE id = ?
            """,
            (memory_id,)
        )

        conn.commit()

        return cursor.rowcount > 0


def clear_all_memories():

    with get_connection() as conn:

        conn.execute(
            "DELETE FROM memories"
        )

        conn.commit()

# ============================================================
# SHORT-TERM CONTEXT
# ============================================================

def save_context(message, emotion=None):

    now = datetime.now().isoformat()

    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS recent_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                emotion TEXT,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute(
            """
            INSERT INTO recent_context
            (message, emotion, created_at)
            VALUES (?, ?, ?)
            """,
            (
                message.strip(),
                emotion,
                now
            )
        )

        conn.commit()


def get_recent_context(limit=30):

    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS recent_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                emotion TEXT,
                created_at TEXT NOT NULL
            )
        """)

        return conn.execute(
            """
            SELECT
                id,
                message,
                emotion,
                created_at
            FROM recent_context
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()


def clear_old_context(days=7):

    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS recent_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                emotion TEXT,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute(
            """
            DELETE FROM recent_context
            WHERE datetime(created_at) <
                  datetime('now', ?)
            """,
            (f"-{days} days",)
        )

        conn.commit()

# ============================================================
# COMPANION PROFILE
# ============================================================

def save_companion_setting(key, value):

    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS companion_profile (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        conn.execute("""
            INSERT INTO companion_profile (key, value)
            VALUES (?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value
        """, (key, value))

        conn.commit()


def get_companion_settings():

    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS companion_profile (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        rows = conn.execute("""
            SELECT key, value
            FROM companion_profile
        """).fetchall()

    return dict(rows)