"""Запуск приложения «Задачи» на Windows (и в PyInstaller-сборке).

Запускает сервер на 127.0.0.1:8010 (или ZADACHI_PORT) и открывает браузер.
Если порт занят - автоматически выбирает следующий свободный (8011, 8012, ...).
"""

import os
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from app.main import app


def _find_free_port(preferred: int) -> int:
    """Вернуть preferred, если он свободен, иначе ближайший свободный (8011..8029),
    иначе любой свободный порт."""
    for port in [preferred, *range(preferred + 1, preferred + 30)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _open_browser(url: str) -> None:
    time.sleep(1.5)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main() -> int:
    port = int(os.environ.get("ZADACHI_PORT", "8010"))
    port = _find_free_port(port)
    url = f"http://127.0.0.1:{port}"

    print("=" * 52)
    print("  Задачи - учёт рабочих задач")
    print(f"  Адрес: {url}")
    print("  Для остановки закройте это окно или нажмите Ctrl+C")
    print("=" * 52)

    threading.Thread(target=_open_browser, args=(url,), daemon=True).start()

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
