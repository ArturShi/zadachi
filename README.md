# Задачи

Одностраничное веб-приложение для учёта рабочих задач.

Поля задачи: **название**, **статус**, **ответственный(ые)**, **примечание**.

## Возможности

- Добавление задачи (форма сверху)
- Изменение статуса прямо из списка (выпадающий список в строке)
- Редактирование и удаление задач
- Фильтр по статусу и поиск по названию / ответственным
- Несколько ответственных через запятую (показываются тегами)
- Тёмная тема, без внешних API (HTMX подключён локально)

Статусы: Новая, В работе, Выполнена, Отложена.

## Стек

FastAPI + Jinja2 + HTMX + SQLite (sqlite3, без ORM).

## Запуск

```bash
# окружение (один раз)
python3 -m venv ~/venvs/zadachi
~/venvs/zadachi/bin/pip install -r requirements.txt

# разработка
cd ~/work/Задачи
~/venvs/zadachi/bin/uvicorn app.main:app --host 0.0.0.0 --port 8010
```

Открыть http://localhost:8010

## Продакшен (systemd)

Пример сервиса `zadachi.service` (автозапуск при загрузке, автоперезапуск
при падении, 2 воркера):

```ini
[Unit]
Description=Zadachi - веб-приложение учёта рабочих задач
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<ваш-пользователь>
WorkingDirectory=<путь-к-проекту>
ExecStart=<путь-к-venv>/bin/uvicorn app.main:app --host 0.0.0.0 --port 8010 --workers 2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now zadachi
sudo systemctl status zadachi   # состояние
sudo journalctl -u zadachi -f   # логи
```

База данных создаётся автоматически в `~/.local/share/zadachi/tasks.db`
(локально, вне сетевого диска - надёжнее). Для тестов путь задаётся
переменной `ZADACHI_DB`.

## Тесты

```bash
cd ~/work/Задачи
~/venvs/zadachi/bin/python -m pytest tests/ -v
```

## Структура

```
Задачи/
├── app/
│   ├── main.py            # маршруты
│   ├── db.py              # работа с SQLite
│   ├── static/htmx.min.js # HTMX локально
│   └── templates/
│       ├── base.html      # каркас + тёмная тема
│       ├── index.html     # одностраничник
│       └── partials/      # список, строка, форма редактирования
├── tests/
│   ├── conftest.py        # изолированная БД + тестовый клиент
│   └── test_tasks.py      # 16 тестов
└── requirements.txt
```
