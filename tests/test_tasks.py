"""Тесты веб-приложения «Задачи»: рабочие задачи с полями
название, статус, ответственный(ые), примечание, дата создания."""

import sqlite3
from datetime import datetime

from app import db

STATUSES = ["Новая", "В работе", "Выполнена", "Отложена"]


def _create(client, name="Подготовить отчёт", responsible="", note="", end_date=""):
    return client.post(
        "/tasks",
        data={"name": name, "responsible": responsible, "note": note, "end_date": end_date},
    )


# ---------- Страница ----------

def test_index_renders_page_with_form_and_fields(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert "Задачи" in body
    assert "Название" in body
    assert "Статус" in body
    assert "Ответственный" in body
    assert "Примечание" in body


def test_index_shows_empty_state(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Нет задач" in r.text


def test_index_lists_all_statuses(client):
    r = client.get("/")
    for s in STATUSES:
        assert s in r.text


# ---------- Создание ----------

def test_create_task_adds_row(client):
    r = _create(
        client,
        name="Согласовать план",
        responsible="Иванов, Петров",
        note="Ждём ответа",
    )
    assert r.status_code == 200
    body = r.text
    assert "Согласовать план" in body
    assert "Иванов" in body and "Петров" in body
    assert "Ждём ответа" in body
    tasks = db.list_tasks()
    assert len(tasks) == 1
    assert tasks[0]["name"] == "Согласовать план"
    assert tasks[0]["status"] == "Новая"
    assert tasks[0]["responsible"] == "Иванов, Петров"
    assert tasks[0]["note"] == "Ждём ответа"


def test_create_task_without_status_uses_default(client):
    r = _create(client, name="Без явного статуса")
    assert r.status_code == 200
    assert "Без явного статуса" in r.text
    assert db.list_tasks()[0]["status"] == "Новая"


def test_create_task_requires_name(client):
    r = _create(client, name="   ")
    assert r.status_code == 422
    assert db.list_tasks() == []


def test_created_task_status_is_new_even_if_status_posted(client):
    """Форма добавления не передаёт статус: присланный статус игнорируется."""
    r = client.post("/tasks", data={"name": "Задача", "status": "В работе"})
    assert r.status_code == 200
    assert db.list_tasks()[0]["status"] == "Новая"


def test_create_form_has_no_status_field(client):
    r = client.get("/")
    body = r.text
    form = body[body.index("Новая задача"):body.index("Список задач")]
    assert "t-status" not in form
    assert 'name="status"' not in form


# ---------- Редактирование ----------

def test_edit_form_is_prefilled(client):
    _create(client, name="Старое имя")
    r = client.get("/tasks/1/edit")
    assert r.status_code == 200
    assert "Старое имя" in r.text


def test_update_task_changes_fields(client):
    _create(client, name="Старое имя")
    r = client.post(
        "/tasks/1",
        data={
            "name": "Новое имя",
            "status": "В работе",
            "responsible": "Сидоров",
            "note": "Готово, проверить",
        },
    )
    assert r.status_code == 200
    body = r.text
    assert "Новое имя" in body
    assert "В работе" in body
    assert "Сидоров" in body
    t = db.get_task(1)
    assert t["name"] == "Новое имя"
    assert t["status"] == "В работе"
    assert t["note"] == "Готово, проверить"


def test_update_to_done_archives_task(client):
    _create(client, name="Доделать и закрыть")
    r = client.post(
        "/tasks/1",
        data={"name": "Доделать и закрыть", "status": "Выполнена", "responsible": "", "note": ""},
    )
    assert r.status_code == 200
    t = db.get_task(1)
    assert t["status"] == "Выполнена"
    assert t["archived"] == 1


def test_change_status_inline(client):
    _create(client, name="Задача со статусом")
    r = client.post("/tasks/1/status", data={"status": "В работе"})
    assert r.status_code == 200
    assert "В работе" in r.text
    assert db.get_task(1)["status"] == "В работе"


def test_status_done_archives_task(client):
    _create(client, name="Выполняемая задача")
    r = client.post("/tasks/1/status", data={"status": "Выполнена"})
    assert r.status_code == 200
    t = db.get_task(1)
    assert t["status"] == "Выполнена"
    assert t["archived"] == 1
    r = client.get("/")
    assert "Выполняемая задача" not in r.text
    r = client.get("/archiv")
    assert "Выполняемая задача" in r.text


def test_status_change_keeps_task_in_main_list(client):
    _create(client, name="Задача в работе")
    client.post("/tasks/1/status", data={"status": "В работе"})
    assert db.get_task(1)["archived"] == 0


def test_status_select_asks_confirmation_for_archive(client):
    _create(client, name="Задача")
    r = client.get("/")
    assert "Перенести задачу" in r.text


# ---------- Удаление ----------

def test_delete_moves_task_to_archive(client):
    _create(client, name="Удалить меня")
    r = client.post("/tasks/1/delete")
    assert r.status_code == 200
    assert db.get_task(1)["archived"] == 1
    r = client.get("/")
    assert "Удалить меня" not in r.text
    r = client.get("/archiv")
    assert "Удалить меня" in r.text


def test_delete_button_mentions_archive(client):
    _create(client, name="Задача")
    r = client.get("/")
    assert "перенесена в Архив" in r.text


# ---------- Фильтр и поиск ----------

def test_filter_by_status(client):
    _create(client, name="Активная задача")
    _create(client, name="Ещё задача")
    client.post("/tasks/1/status", data={"status": "В работе"})
    r = client.get("/tasks", params={"status": "В работе"})
    assert "Активная задача" in r.text
    assert "Ещё задача" not in r.text


def test_search_by_name(client):
    _create(client, name="Подготовить презентацию")
    _create(client, name="Созвониться с подрядчиком")
    r = client.get("/tasks", params={"q": "презентац"})
    assert "Подготовить презентацию" in r.text
    assert "Созвониться" not in r.text


def test_search_by_responsible(client):
    _create(client, name="Задача Кузнецова", responsible="Кузнецов")
    _create(client, name="Задача Смирновой", responsible="Смирнова")
    r = client.get("/tasks", params={"q": "смирнова"})
    assert "Задача Смирновой" in r.text
    assert "Задача Кузнецова" not in r.text


# ---------- Несколько ответственных ----------

def test_multiple_responsibles_rendered_as_tags(client):
    _create(client, name="Общая задача", responsible="Иванов, Петров; Сидорова")
    r = client.get("/")
    body = r.text
    for name in ("Иванов", "Петров", "Сидорова"):
        assert name in body


def test_responsible_may_be_empty(client):
    _create(client, name="Задача без ответственного")
    r = client.get("/")
    assert "Задача без ответственного" in r.text
    assert db.list_tasks()[0]["responsible"] == ""


# ---------- Дата создания (автоматическая, ДД.ММ.ГГ) ----------

def test_index_shows_created_date_column_before_name(client):
    _create(client, name="Задача")
    r = client.get("/")
    body = r.text
    head = body[body.index("<thead>"):]
    assert head.index("Создана") < head.index("Название")


# ---------- Окончание (срок, ДД.ММ.ГГ) ----------

def test_index_shows_end_date_column_between_created_and_name(client):
    _create(client, name="Задача")
    r = client.get("/")
    head = r.text[r.text.index("<thead>"):]
    assert head.index("Создана") < head.index("Окончание") < head.index("Название")


def test_create_task_with_end_date(client):
    r = _create(client, name="Задача со сроком", end_date="25.08.26")
    assert r.status_code == 200
    assert "25.08.26" in r.text
    assert db.list_tasks()[0]["end_date"] == "25.08.26"


def test_create_task_with_iso_end_date(client):
    r = _create(client, name="Задача со сроком", end_date="2026-08-25")
    assert r.status_code == 200
    assert db.list_tasks()[0]["end_date"] == "25.08.26"


def test_end_date_field_is_date_picker(client):
    r = client.get("/")
    body = r.text
    form = body[body.index("Новая задача"):body.index("Список задач")]
    assert 'name="end_date"' in form
    assert 'type="date"' in form


def test_create_task_without_end_date_is_empty(client):
    r = _create(client, name="Задача без срока")
    assert r.status_code == 200
    assert db.list_tasks()[0]["end_date"] == ""


def test_create_task_rejects_invalid_end_date(client):
    r = _create(client, name="Плохой срок", end_date="25.08.2026")
    assert r.status_code == 422
    assert db.list_tasks() == []


def test_edit_form_shows_end_date_in_iso(client):
    _create(client, name="Задача со сроком", end_date="25.08.26")
    r = client.get("/tasks/1/edit")
    assert r.status_code == 200
    assert 'value="2026-08-25"' in r.text


def test_update_task_changes_end_date(client):
    _create(client, name="Задача")
    r = client.post(
        "/tasks/1",
        data={"name": "Задача", "status": "Новая", "responsible": "", "note": "", "end_date": "30.08.26"},
    )
    assert r.status_code == 200
    assert db.get_task(1)["end_date"] == "30.08.26"


def test_migration_adds_end_date_to_existing_db(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE tasks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'Новая',
            responsible  TEXT NOT NULL DEFAULT '',
            note         TEXT NOT NULL DEFAULT '',
            created_date TEXT NOT NULL DEFAULT '',
            archived     INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.execute("INSERT INTO tasks (name) VALUES ('Старая задача')")
    conn.commit()
    conn.close()

    monkeypatch.setenv("ZADACHI_DB", str(path))
    db.init_db()
    db.init_db()  # повторный вызов не должен падать (идемпотентность)

    cols = [r[1] for r in db.get_conn().execute("PRAGMA table_info(tasks)")]
    assert "end_date" in cols
    assert db.get_task(1)["end_date"] == ""


def test_create_task_stores_actual_date(client):
    r = _create(client, name="Задача с датой")
    assert r.status_code == 200
    today = datetime.now().strftime("%d.%m.%y")
    assert db.list_tasks()[0]["created_date"] == today


def test_created_date_shown_in_list_before_name(client):
    _create(client, name="Задача с датой")
    r = client.get("/")
    body = r.text
    today = datetime.now().strftime("%d.%m.%y")
    assert body.index(today) < body.index("Задача с датой")


def test_edit_keeps_created_date(client):
    _create(client, name="Задача")
    original = db.list_tasks()[0]["created_date"]
    r = client.post(
        "/tasks/1",
        data={"name": "Новое имя", "status": "В работе", "responsible": "", "note": ""},
    )
    assert r.status_code == 200
    t = db.get_task(1)
    assert t["name"] == "Новое имя"
    assert t["created_date"] == original


def test_migration_backfills_created_date(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'Новая',
            responsible TEXT NOT NULL DEFAULT '',
            note        TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.execute(
        "INSERT INTO tasks (name, status, created_at) VALUES ('Старая задача', 'Новая', '2026-08-10 09:00:00')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("ZADACHI_DB", str(path))
    db.init_db()

    cols = [r[1] for r in db.get_conn().execute("PRAGMA table_info(tasks)")]
    assert "created_date" in cols
    t = db.get_task(1)
    assert t["name"] == "Старая задача"
    assert t["created_date"] == "10.08.26"


# ---------- Архив ----------

def test_archive_page_exists(client):
    r = client.get("/archiv")
    assert r.status_code == 200
    assert "Архив" in r.text


def test_archive_page_shows_empty_state(client):
    r = client.get("/archiv")
    assert "Нет задач" in r.text


def test_archiv_shows_task_list_panel(client):
    r = client.get("/archiv")
    assert "Список задач" in r.text


def test_archiv_has_filter_like_main(client):
    r = client.get("/archiv")
    body = r.text
    assert 'name="status"' in body
    assert 'name="q"' in body
    assert "Применить" in body


def test_archiv_filter_by_status(client):
    _create(client, name="Архивная активная")
    _create(client, name="Архивная готовая")
    client.post("/tasks/1/archive")
    client.post("/tasks/2/archive")
    client.post("/tasks/1/status", data={"status": "В работе"})
    client.post("/tasks/2/status", data={"status": "Отложена"})
    r = client.get("/archiv/tasks", params={"status": "В работе"})
    assert "Архивная активная" in r.text
    assert "Архивная готовая" not in r.text


def test_main_count_excludes_archived(client):
    _create(client, name="Активная")
    _create(client, name="Задача в архив")
    client.post("/tasks/2/archive")
    r = client.get("/")
    assert 'class="count">1 шт.' in r.text


def test_archive_count_matches_archived_tasks(client):
    _create(client, name="Активная")
    _create(client, name="В архив 1")
    _create(client, name="В архив 2")
    client.post("/tasks/2/archive")
    client.post("/tasks/3/archive")
    r = client.get("/archiv")
    assert 'class="count">2 шт.' in r.text


def test_archive_button_above_apply_with_danger_style(client):
    r = client.get("/")
    body = r.text
    assert body.index("Архив") < body.index("Применить")
    seg = body[:body.index("Применить")]
    assert "btn-danger" in seg


def test_archive_moves_task_out_of_main_list(client):
    _create(client, name="Задача в архив")
    r = client.post("/tasks/1/archive")
    assert r.status_code == 200
    assert db.get_task(1)["archived"] == 1
    r = client.get("/")
    assert "Задача в архив" not in r.text


def test_archived_task_shows_on_archive_page(client):
    _create(client, name="Задача в архив")
    client.post("/tasks/1/archive")
    r = client.get("/archiv")
    assert "Задача в архив" in r.text


def test_main_list_excludes_archived(client):
    _create(client, name="Активная")
    _create(client, name="Задача в архив")
    client.post("/tasks/2/archive")
    r = client.get("/")
    assert "Активная" in r.text
    assert "Задача в архив" not in r.text


def test_unarchive_returns_task_to_main_list(client):
    _create(client, name="Вернуть из архива")
    client.post("/tasks/1/archive")
    r = client.post("/archiv/tasks/1/unarchive")
    assert r.status_code == 200
    assert db.get_task(1)["archived"] == 0
    r = client.get("/")
    assert "Вернуть из архива" in r.text


def test_delete_from_archive(client):
    _create(client, name="Удалить из архива")
    client.post("/tasks/1/archive")
    r = client.post("/archiv/tasks/1/delete")
    assert r.status_code == 200
    assert db.list_tasks() == []
