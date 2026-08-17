"""Веб-приложение «Задачи»: учёт рабочих задач.

Стек: FastAPI + Jinja2 + HTMX + SQLite, тёмная тема, без внешних API.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

STATUS_CLASS = {
    "Новая": "new",
    "В работе": "work",
    "Выполнена": "done",
    "Отложена": "hold",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Задачи", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def split_responsibles(raw: str) -> list[str]:
    """'Иванов, Петров; Сидорова' -> ['Иванов', 'Петров', 'Сидорова']."""
    parts = [p.strip() for p in raw.replace(";", ",").replace("\n", ",").split(",")]
    return [p for p in parts if p]


def _ctx(request: Request, **extra) -> dict:
    ctx = {
        "request": request,
        "statuses": db.STATUSES,
        "status_class": STATUS_CLASS,
        "split_responsibles": split_responsibles,
        "count": len(db.list_tasks()),
    }
    ctx.update(extra)
    return ctx


def _validate(name: str) -> str:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название задачи обязательно")
    return name


def _validate_status(status: str) -> str:
    if status not in db.STATUSES:
        raise HTTPException(status_code=422, detail="Недопустимый статус")
    return status


def _validate_end_date(end_date: str) -> str:
    """Пустая строка допустима (срок не задан).

    Принимает формат календаря ГГГГ-ММ-ДД и ДД.ММ.ГГ, хранит как ДД.ММ.ГГ.
    """
    end_date = end_date.strip()
    if not end_date:
        return ""
    try:
        if "-" in end_date:
            d = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            d = datetime.strptime(end_date, "%d.%m.%y")
    except ValueError:
        raise HTTPException(
            status_code=422, detail="Окончание должно быть в формате ДД.ММ.ГГ"
        )
    return d.strftime("%d.%m.%y")


def _to_iso(date_str: str) -> str:
    """'25.08.26' -> '2026-08-25' (для value в input type=date)."""
    if not date_str:
        return ""
    try:
        return datetime.strptime(date_str, "%d.%m.%y").strftime("%Y-%m-%d")
    except ValueError:
        return ""


templates.env.filters["to_iso"] = _to_iso


# ---------- Страницы ----------

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    tasks = db.list_tasks(archived=False)
    return templates.TemplateResponse(
        request, "index.html", _ctx(request, tasks=tasks, status="", q="")
    )


@app.get("/tasks", response_class=HTMLResponse)
def list_partial(request: Request, status: str = Query(""), q: str = Query("")):
    tasks = db.list_tasks(status=status or None, q=q or None, archived=False)
    return templates.TemplateResponse(
        request, "partials/task_list.html", _ctx(request, tasks=tasks, status=status, q=q)
    )


@app.get("/archiv", response_class=HTMLResponse)
def archiv_page(request: Request):
    tasks = db.list_tasks(archived=True)
    return templates.TemplateResponse(
        request, "archiv.html", _ctx(request, tasks=tasks, count=len(tasks))
    )


@app.get("/archiv/tasks", response_class=HTMLResponse)
def archiv_list_partial(request: Request, status: str = Query(""), q: str = Query("")):
    tasks = db.list_tasks(status=status or None, q=q or None, archived=True)
    return templates.TemplateResponse(
        request, "partials/archiv_list.html", _ctx(request, tasks=tasks, status=status, q=q, count=len(tasks))
    )


# ---------- Задачи ----------

@app.post("/tasks", response_class=HTMLResponse)
def create_task(
    request: Request,
    name: str = Form(...),
    responsible: str = Form(""),
    note: str = Form(""),
    end_date: str = Form(""),
):
    name = _validate(name)
    end_date = _validate_end_date(end_date)
    db.create_task(name, "Новая", responsible.strip(), note.strip(), end_date)
    tasks = db.list_tasks(archived=False)
    return templates.TemplateResponse(
        request, "partials/task_list.html", _ctx(request, tasks=tasks)
    )


@app.get("/tasks/{task_id}", response_class=HTMLResponse)
def row_partial(request: Request, task_id: int):
    t = db.get_task(task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return templates.TemplateResponse(
        request, "partials/task_row.html", _ctx(request, t=t)
    )


@app.get("/tasks/{task_id}/edit", response_class=HTMLResponse)
def edit_form(request: Request, task_id: int):
    t = db.get_task(task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return templates.TemplateResponse(
        request, "partials/task_edit.html", _ctx(request, t=t)
    )


@app.post("/tasks/{task_id}", response_class=HTMLResponse)
def update_task(
    request: Request,
    task_id: int,
    name: str = Form(...),
    status: str = Form(...),
    responsible: str = Form(""),
    note: str = Form(""),
    end_date: str = Form(""),
):
    name = _validate(name)
    status = _validate_status(status)
    end_date = _validate_end_date(end_date)
    db.update_task(task_id, name, status, responsible.strip(), note.strip(), end_date)
    if status == "Выполнена":
        db.archive_task(task_id)
    tasks = db.list_tasks(archived=False)
    return templates.TemplateResponse(
        request, "partials/task_list.html", _ctx(request, tasks=tasks)
    )


@app.post("/tasks/{task_id}/status", response_class=HTMLResponse)
def change_status(request: Request, task_id: int, status: str = Form(...)):
    status = _validate_status(status)
    db.update_status(task_id, status)
    if status == "Выполнена":
        db.archive_task(task_id)
    tasks = db.list_tasks(archived=False)
    return templates.TemplateResponse(
        request, "partials/task_list.html", _ctx(request, tasks=tasks)
    )


@app.post("/tasks/{task_id}/delete", response_class=HTMLResponse)
def delete_task(request: Request, task_id: int):
    db.archive_task(task_id)
    tasks = db.list_tasks(archived=False)
    return templates.TemplateResponse(
        request, "partials/task_list.html", _ctx(request, tasks=tasks)
    )


@app.post("/tasks/{task_id}/archive", response_class=HTMLResponse)
def archive_task(request: Request, task_id: int):
    db.archive_task(task_id)
    tasks = db.list_tasks(archived=False)
    return templates.TemplateResponse(
        request, "partials/task_list.html", _ctx(request, tasks=tasks)
    )


@app.post("/archiv/tasks/{task_id}/unarchive", response_class=HTMLResponse)
def unarchive_task(request: Request, task_id: int):
    db.unarchive_task(task_id)
    tasks = db.list_tasks(archived=True)
    return templates.TemplateResponse(
        request, "partials/archiv_list.html", _ctx(request, tasks=tasks)
    )


@app.post("/archiv/tasks/{task_id}/delete", response_class=HTMLResponse)
def delete_archived_task(request: Request, task_id: int):
    db.delete_task(task_id)
    tasks = db.list_tasks(archived=True)
    return templates.TemplateResponse(
        request, "partials/archiv_list.html", _ctx(request, tasks=tasks)
    )
