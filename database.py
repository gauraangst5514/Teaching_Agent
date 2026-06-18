"""
Async SQLite database module for the Teacher Assistant app.

Provides table creation, CRUD helpers for submissions and feedback,
and a dashboard statistics query — all using aiosqlite for async compatibility.
"""

import json
import aiosqlite
from datetime import datetime, timezone
from typing import Any, Optional

from config import ta_config

DB_PATH: str = ta_config.DB_PATH


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_SUBMISSIONS = """
CREATE TABLE IF NOT EXISTS submissions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_name    TEXT NOT NULL,
    submission_type TEXT NOT NULL CHECK(submission_type IN ('notebook', 'assignment', 'solution', 'question', 'youtube')),
    file_path       TEXT,
    original_text   TEXT,
    extracted_text  TEXT,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'processing', 'completed', 'failed')),
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_FEEDBACK = """
CREATE TABLE IF NOT EXISTS feedback (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id     INTEGER NOT NULL,
    correctness_score INTEGER CHECK(correctness_score BETWEEN 0 AND 100),
    mistakes_json     TEXT,
    explanation       TEXT,
    suggestions       TEXT,
    overall_feedback  TEXT,
    agent_log         TEXT,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
);
"""

_CREATE_CHATS = """
CREATE TABLE IF NOT EXISTS submission_chats (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL,
    role          TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content       TEXT NOT NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
);
"""


async def _get_db() -> aiosqlite.Connection:
    """Open (or reuse) a database connection with row-factory enabled."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("PRAGMA foreign_keys=ON;")
    return db


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

async def init_db() -> None:
    """Create the submissions and feedback tables if they do not exist."""
    db = await _get_db()
    try:
        await db.execute(_CREATE_SUBMISSIONS)
        await db.execute(_CREATE_FEEDBACK)
        await db.execute(_CREATE_CHATS)
        await db.commit()
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Submissions helpers
# ---------------------------------------------------------------------------

async def create_submission(
    student_name: str,
    submission_type: str,
    file_path: Optional[str] = None,
    original_text: Optional[str] = None,
    status: str = "pending",
) -> int:
    """Insert a new submission and return its id."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            """
            INSERT INTO submissions (student_name, submission_type, file_path, original_text, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                student_name,
                submission_type,
                file_path,
                original_text,
                status,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]
    finally:
        await db.close()


async def update_submission(
    submission_id: int,
    **fields: Any,
) -> None:
    """Update one or more columns on an existing submission row.

    Usage:
        await update_submission(1, status='processing', extracted_text='...')
    """
    allowed = {
        "student_name",
        "submission_type",
        "file_path",
        "original_text",
        "extracted_text",
        "status",
    }
    to_set = {k: v for k, v in fields.items() if k in allowed}
    if not to_set:
        return

    set_clause = ", ".join(f"{col} = ?" for col in to_set)
    values = list(to_set.values()) + [submission_id]

    db = await _get_db()
    try:
        await db.execute(
            f"UPDATE submissions SET {set_clause} WHERE id = ?",  # noqa: S608
            values,
        )
        await db.commit()
    finally:
        await db.close()


async def get_submission(submission_id: int) -> Optional[dict[str, Any]]:
    """Return a single submission as a dict, or None."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_all_submissions() -> list[dict[str, Any]]:
    """Return all submissions ordered by most recent first."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM submissions ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Feedback helpers
# ---------------------------------------------------------------------------

async def create_feedback(
    submission_id: int,
    correctness_score: int = 0,
    mistakes_json: Optional[str] = None,
    explanation: Optional[str] = None,
    suggestions: Optional[str] = None,
    overall_feedback: Optional[str] = None,
    agent_log: Optional[str] = None,
) -> int:
    """Insert a feedback record and return its id."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            """
            INSERT INTO feedback
                (submission_id, correctness_score, mistakes_json, explanation,
                 suggestions, overall_feedback, agent_log, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                submission_id,
                correctness_score,
                mistakes_json,
                explanation,
                suggestions,
                overall_feedback,
                agent_log,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]
    finally:
        await db.close()


async def get_feedback_for_submission(
    submission_id: int,
) -> list[dict[str, Any]]:
    """Return all feedback records for a given submission."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM feedback WHERE submission_id = ? ORDER BY created_at DESC",
            (submission_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Dashboard / analytics
# ---------------------------------------------------------------------------

async def get_dashboard_stats() -> dict[str, Any]:
    """Aggregate statistics for the dashboard view."""
    db = await _get_db()
    try:
        # Total submissions
        cur = await db.execute("SELECT COUNT(*) AS cnt FROM submissions")
        total_submissions = (await cur.fetchone())["cnt"]

        # By status
        cur = await db.execute(
            "SELECT status, COUNT(*) AS cnt FROM submissions GROUP BY status"
        )
        status_counts: dict[str, int] = {row["status"]: row["cnt"] for row in await cur.fetchall()}

        # By type
        cur = await db.execute(
            "SELECT submission_type, COUNT(*) AS cnt FROM submissions GROUP BY submission_type"
        )
        type_counts: dict[str, int] = {row["submission_type"]: row["cnt"] for row in await cur.fetchall()}

        # Average correctness score
        cur = await db.execute(
            "SELECT AVG(correctness_score) AS avg_score FROM feedback"
        )
        avg_row = await cur.fetchone()
        avg_score = round(avg_row["avg_score"], 1) if avg_row["avg_score"] is not None else 0.0

        # Recent submissions (last 10)
        cur = await db.execute(
            "SELECT * FROM submissions ORDER BY created_at DESC LIMIT 10"
        )
        recent = [dict(r) for r in await cur.fetchall()]

        return {
            "total_submissions": total_submissions,
            "status_counts": status_counts,
            "type_counts": type_counts,
            "average_correctness_score": avg_score,
            "recent_submissions": recent,
        }
    finally:
        await db.close()

# ---------------------------------------------------------------------------
# Chat helpers
# ---------------------------------------------------------------------------

async def add_chat_message(submission_id: int, role: str, content: str) -> None:
    """Insert a new chat message for a submission."""
    db = await _get_db()
    try:
        await db.execute(
            """
            INSERT INTO submission_chats (submission_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (submission_id, role, content, datetime.now(timezone.utc).isoformat())
        )
        await db.commit()
    finally:
        await db.close()

async def get_chat_history(submission_id: int) -> list[dict[str, Any]]:
    """Retrieve all chat messages for a specific submission in chronological order."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            """
            SELECT id, role, content, created_at
            FROM submission_chats
            WHERE submission_id = ?
            ORDER BY created_at ASC
            """,
            (submission_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()
