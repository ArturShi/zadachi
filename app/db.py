"""Работа с базой данных SQLite: таблица задач."""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

STATUSES = ["Новая", "В работе", "Выполнена", "Отложена"]

if os.name == "nt":
    # Windows: база в %LOCALAPPDATA%\Zadachi\tasks.db (переживает переустановку)
    _DEFAULT_DB = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Zadachi" / "tasks.db"
else:
    _DEFAULT_DB = Path.home() / ".local" / "share" / "zadachi" / "tasks.db"


def db_path() -> Path:
    """Путь к файлу БД: переопределяется переменной ZADACHI_DB (для тестов)."""
    return Path(os.environ.get("ZADACHI_DB", str(_DEFAULT_DB)))


def get_conn() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'Новая',
                responsible  TEXT NOT NULL DEFAULT '',
                note         TEXT NOT NULL DEFAULT '',
                created_date TEXT NOT NULL DEFAULT '',
                end_date     TEXT NOT NULL DEFAULT '',
                archived     INTEGER NOT NULL DEFAULT 0,
                created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        # Миграции: добавляют недостающие колонки в старые базы.
        # Идемпотентны и устойчивы к гонке воркеров (duplicate column -> пропуск).
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)")]
        if "created_date" not in cols:
            try:
                conn.execute("ALTER TABLE tasks ADD COLUMN created_date TEXT NOT NULL DEFAULT ''")
                rows = conn.execute("SELECT id, created_at FROM tasks").fetchall()
                for task_id, created_at in rows:
                    try:
                        d = datetime.strptime(created_at[:10], "%Y-%m-%d").strftime("%d.%m.%y")
                    except ValueError:
                        d = datetime.now().strftime("%d.%m.%y")
                    conn.execute(
                        "UPDATE tasks SET created_date = ? WHERE id = ?", (d, task_id)
                    )
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e):
                    raise
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)")]
        if "archived" not in cols:
            try:
                conn.execute("ALTER TABLE tasks ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e):
                    raise
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)")]
        if "end_date" not in cols:
            try:
                conn.execute("ALTER TABLE tasks ADD COLUMN end_date TEXT NOT NULL DEFAULT ''")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e):
                    raise


def _today() -> str:
    """Сегодняшняя дата в формате ДД.ММ.ГГ (без времени)."""
    return datetime.now().strftime("%d.%m.%y")


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "status": row["status"],
        "responsible": row["responsible"],
        "note": row["note"],
        "created_date": row["created_date"] or "",
        "end_date": row["end_date"] or "",
        "archived": row["archived"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_tasks(status: str | None = None, q: str | None = None, archived: bool = False) -> list[dict]:
    """Задачи, при необходимости отфильтрованные по статусу, поиску и архиву.

    Поиск регистронезависимый (casefold), ищет по названию и ответственным.
    """
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
    tasks = [_row_to_dict(r) for r in rows]
    tasks = [t for t in tasks if (t["archived"] == 1) == archived]
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    if q and q.strip():
        needle = q.strip().casefold()
        tasks = [
            t
            for t in tasks
            if needle in t["name"].casefold() or needle in t["responsible"].casefold()
        ]
    return tasks


def get_task(task_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _row_to_dict(row) if row else None


def create_task(name: str, status: str, responsible: str, note: str, end_date: str = "") -> int:
    """Создаёт задачу; дата создания проставляется автоматически (ДД.ММ.ГГ)."""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (name, status, responsible, note, created_date, end_date) VALUES (?, ?, ?, ?, ?, ?)",
            (name, status, responsible, note, _today(), end_date),
        )
        return cur.lastrowid


def update_task(task_id: int, name: str, status: str, responsible: str, note: str, end_date: str = "") -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE tasks
               SET name = ?, status = ?, responsible = ?, note = ?, end_date = ?,
                   updated_at = datetime('now', 'localtime')
             WHERE id = ?
            """,
            (name, status, responsible, note, end_date, task_id),
        )


def update_status(task_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE tasks
               SET status = ?, updated_at = datetime('now', 'localtime')
             WHERE id = ?
            """,
            (status, task_id),
        )


def delete_task(task_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def archive_task(task_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET archived = 1, updated_at = datetime('now', 'localtime') WHERE id = ?",
            (task_id,),
        )


def unarchive_task(task_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET archived = 0, updated_at = datetime('now', 'localtime') WHERE id = ?",
            (task_id,),
        )
