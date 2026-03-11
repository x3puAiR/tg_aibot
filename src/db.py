from __future__ import annotations

import time

import aiosqlite


class Database:
    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                provider TEXT,
                apikey TEXT,
                model TEXT,
                current_session_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT 'New session',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tokens INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );
        """)
        # Migrate existing installs: add current_session_id if upgrading
        try:
            await self._conn.execute("ALTER TABLE users ADD COLUMN current_session_id INTEGER")
        except Exception:
            pass
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    # ── User ────────────────────────────────────────────────────────

    async def get_user(self, user_id: int) -> dict:
        assert self._conn is not None
        async with self._conn.execute(
            "SELECT provider, apikey, model, current_session_id FROM users WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return {"provider": None, "apikey": None, "model": None, "current_session_id": None}
        return {
            "provider": row[0],
            "apikey": row[1],
            "model": row[2],
            "current_session_id": row[3],
        }

    async def set_field(self, user_id: int, field: str, value: str | int | None) -> None:
        if field not in {"provider", "apikey", "model", "current_session_id"}:
            raise ValueError(f"Invalid field: {field}")
        assert self._conn is not None
        await self._conn.execute(
            """
            INSERT INTO users (user_id, provider, apikey, model, current_session_id)
            VALUES (?, NULL, NULL, NULL, NULL)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (user_id,),
        )
        await self._conn.execute(
            f"UPDATE users SET {field} = ? WHERE user_id = ?",
            (value, user_id),
        )
        await self._conn.commit()

    # ── Sessions ────────────────────────────────────────────────────

    async def create_session(self, user_id: int, title: str = "New session") -> int:
        assert self._conn is not None
        now = int(time.time())
        async with self._conn.execute(
            "INSERT INTO sessions (user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (user_id, title, now, now),
        ) as cursor:
            session_id = cursor.lastrowid
        assert session_id is not None
        await self._conn.execute(
            """
            INSERT INTO users (user_id, provider, apikey, model, current_session_id)
            VALUES (?, NULL, NULL, NULL, ?)
            ON CONFLICT(user_id) DO UPDATE SET current_session_id = ?
            """,
            (user_id, session_id, session_id),
        )
        await self._conn.commit()
        return session_id

    async def get_sessions(self, user_id: int, limit: int = 10) -> list[dict]:
        assert self._conn is not None
        async with self._conn.execute(
            """
            SELECT session_id, title, created_at, updated_at
            FROM sessions WHERE user_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            {"session_id": r[0], "title": r[1], "created_at": r[2], "updated_at": r[3]}
            for r in rows
        ]

    async def get_session(self, session_id: int) -> dict | None:
        assert self._conn is not None
        async with self._conn.execute(
            "SELECT session_id, user_id, title, created_at, updated_at FROM sessions WHERE session_id = ?",
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return {
            "session_id": row[0],
            "user_id": row[1],
            "title": row[2],
            "created_at": row[3],
            "updated_at": row[4],
        }

    async def delete_session(self, session_id: int) -> None:
        assert self._conn is not None
        await self._conn.execute(
            "UPDATE users SET current_session_id = NULL WHERE current_session_id = ?",
            (session_id,),
        )
        await self._conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        await self._conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await self._conn.commit()

    async def set_session_title(self, session_id: int, title: str) -> None:
        assert self._conn is not None
        await self._conn.execute(
            "UPDATE sessions SET title = ? WHERE session_id = ?",
            (title, session_id),
        )
        await self._conn.commit()

    # ── Messages ────────────────────────────────────────────────────

    async def add_message(
        self, session_id: int, role: str, content: str, tokens: int = 0
    ) -> None:
        assert self._conn is not None
        now = int(time.time())
        await self._conn.execute(
            "INSERT INTO messages (session_id, role, content, tokens, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, tokens, now),
        )
        await self._conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        await self._conn.commit()

    async def get_messages(self, session_id: int) -> list[dict]:
        assert self._conn is not None
        async with self._conn.execute(
            """
            SELECT role, content FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC, message_id ASC
            """,
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [{"role": r[0], "content": r[1]} for r in rows]

    async def get_session_tokens(self, session_id: int) -> int:
        assert self._conn is not None
        async with self._conn.execute(
            "SELECT COALESCE(SUM(tokens), 0) FROM messages WHERE session_id = ?",
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return int(row[0]) if row else 0
