#!/usr/bin/env bash
# Установка приложения «Задачи» на Ubuntu одной командой.
#
# Варианты запуска:
#   1) Из клонированного репозитория:  bash install.sh
#   2) Из интернета (код скачается сам): bash <(curl -s https://raw.githubusercontent.com/ArturShi/zadachi/main/install.sh)
#
# Опции окружения:
#   ZADACHI_PORT=8080         другой порт (по умолчанию 8010)
#   ZADACHI_NO_SYSTEMD=1      только код и окружение, без сервиса автозапуска
set -euo pipefail

APP_NAME="zadachi"
PORT="${ZADACHI_PORT:-8010}"
REPO_URL="https://github.com/ArturShi/zadachi.git"
NO_SYSTEMD="${ZADACHI_NO_SYSTEMD:-0}"

# Реальный пользователь и его домашняя директория (если запущено через sudo)
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
  RUN_USER="$SUDO_USER"
  RUN_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
else
  RUN_USER="${USER:-$(id -un)}"
  RUN_HOME="$HOME"
fi

# sudo нужен только для системных операций (apt, systemd); под root не нужен
if [ "$(id -u)" = "0" ]; then
  SUDO=""
else
  SUDO="sudo"
fi

step() { echo; echo "==> $1"; }

# 1. Директория проекта: текущая, либо ~/zadachi (клонируем при необходимости)
step "1/5 Проект"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || true)"
if [ -f "$SCRIPT_DIR/app/main.py" ]; then
  APP_DIR="$SCRIPT_DIR"
  echo "Использую текущую директорию: $APP_DIR"
else
  APP_DIR="$RUN_HOME/$APP_NAME"
  if [ ! -d "$APP_DIR/.git" ]; then
    echo "Клонирую репозиторий в $APP_DIR ..."
    git clone "$REPO_URL" "$APP_DIR"
  else
    echo "Репозиторий уже есть, обновляю: $APP_DIR"
    git -C "$APP_DIR" pull --ff-only || true
  fi
fi

# 2. Python и модуль venv
step "2/5 Python"
if ! command -v python3 >/dev/null 2>&1; then
  $SUDO apt-get update
  $SUDO apt-get install -y python3
fi
if ! python3 -c 'import venv' >/dev/null 2>&1; then
  $SUDO apt-get install -y python3-venv
fi
echo "python3: $(python3 --version)"

# 3. Виртуальное окружение и зависимости
step "3/5 Окружение и зависимости"
VENV_DIR="$RUN_HOME/venvs/$APP_NAME"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "Создаю виртуальное окружение: $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
echo "Зависимости установлены"

# 4. Сервис автозапуска (systemd)
if [ "$NO_SYSTEMD" = "1" ]; then
  step "4/5 Пропущено (ZADACHI_NO_SYSTEMD=1)"
else
  step "4/5 Сервис автозапуска"
  UNIT="/etc/systemd/system/$APP_NAME.service"
  $SUDO tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=Zadachi - веб-приложение учёта рабочих задач
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_USER
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable --now "$APP_NAME" >/dev/null
  echo "Сервис $APP_NAME зарегистрирован и запущен"
fi

# 5. Проверка
step "5/5 Проверка"
if [ "$NO_SYSTEMD" = "1" ]; then
  echo "Dry-run: сервис не запускался."
  echo "Запуск вручную: $VENV_DIR/bin/uvicorn app.main:app --host 0.0.0.0 --port $PORT"
else
  sleep 2
  if curl -sf "http://localhost:$PORT" >/dev/null 2>&1; then
    echo "Готово! Приложение работает: http://localhost:$PORT"
    echo "Состояние: systemctl status $APP_NAME   Логи: journalctl -u $APP_NAME -f"
  else
    echo "Ошибка: приложение не отвечает на порту $PORT"
    echo "Смотрите логи: journalctl -u $APP_NAME -f"
    exit 1
  fi
fi

echo
echo "Установка завершена. Код: $APP_DIR"
