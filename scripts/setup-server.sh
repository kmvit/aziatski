#!/usr/bin/env bash
#
# Универсальная настройка Ubuntu под любой Django-проект:
#   - обновление системы, установка пакетов (nginx, postgresql, python3-venv)
#   - создание БД и пользователя PostgreSQL
#   - проект в APP_DIR: venv, зависимости, миграции, статика
#   - Gunicorn (systemd)
#   - Nginx (конфиг сайта)
#
# Запуск (на сервере):
#   sudo bash setup-server.sh
#
# Переменные (задать до запуска или ввести по запросу):
#   APP_DIR           — каталог приложения (по умолчанию: корень проекта, где лежит этот скрипт)
#   PROJECT_NAME      — имя проекта (для имен файлов/сервисов)
#   DOMAIN            — домен или IP (например example.com)
#   APP_SCHEME        — http/https (по умолчанию https)
#   DB_NAME           — имя БД PostgreSQL
#   DB_USER           — пользователь БД PostgreSQL
#   DB_PASSWORD       — пароль пользователя БД
#   DB_HOST           — хост БД (по умолчанию localhost)
#   DB_PORT           — порт БД (по умолчанию 5432)
#   DJANGO_SECRET     — DJANGO_SECRET_KEY для продакшена
#   DJANGO_DIR        — относительный путь до каталога с manage.py
#   REQUIREMENTS_FILE — относительный путь до requirements.txt
#   WSGI_MODULE       — python-путь до WSGI app, например config.wsgi:application
#   STATIC_ROOT       — абсолютный путь до staticfiles (по умолчанию APP_DIR/DJANGO_DIR/staticfiles)
#   MEDIA_ROOT        — абсолютный путь до media (по умолчанию APP_DIR/DJANGO_DIR/media)
#   FRONTEND_DIR      — относительный путь до фронтенда с package.json (по умолчанию frontend, если найден)
#   FRONTEND_BUILD_DIR — путь до собранного фронта (по умолчанию FRONTEND_DIR/dist)
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
DEFAULT_APP_DIR="$(dirname "${SCRIPT_DIR}")"
APP_DIR="${APP_DIR:-${DEFAULT_APP_DIR}}"
SERVICE_USER="${SERVICE_USER:-www-data}"
APP_SCHEME="${APP_SCHEME:-https}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-3}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"
export DEBIAN_FRONTEND="${DEBIAN_FRONTEND:-noninteractive}"

slugify() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]' '_' | sed 's/^_//; s/_$//'
}

detect_wsgi_module() {
  local django_root="$1"
  local manage_py="$django_root/manage.py"
  python3 - "$django_root" "$manage_py" <<'PY'
import os
import re
import sys

django_root = sys.argv[1]
path = sys.argv[2]

# 1) Надёжный путь: находим реальный wsgi.py в дереве проекта.
wsgi_candidates = []
for root, dirs, files in os.walk(django_root):
    dirs[:] = [d for d in dirs if d not in {".venv", "venv", "__pycache__", ".git", "node_modules"}]
    if "wsgi.py" in files:
        full_path = os.path.join(root, "wsgi.py")
        rel_path = os.path.relpath(full_path, django_root)
        mod = rel_path[:-3].replace(os.sep, ".")
        if mod:
            wsgi_candidates.append(mod)

if len(wsgi_candidates) == 1:
    print(f"{wsgi_candidates[0]}:application")
    raise SystemExit(0)
elif len(wsgi_candidates) > 1:
    # Предпочитаем классический вариант <package>.wsgi
    preferred = [m for m in wsgi_candidates if m.endswith(".wsgi") and ".settings." not in m]
    if preferred:
        print(f"{sorted(preferred, key=len)[0]}:application")
        raise SystemExit(0)
    print(f"{sorted(wsgi_candidates, key=len)[0]}:application")
    raise SystemExit(0)

# 2) Fallback: пробуем вывести модуль из DJANGO_SETTINGS_MODULE в manage.py.
try:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
except OSError:
    print("")
    raise SystemExit(0)

m = re.search(
    r"os\.environ\.setdefault\(\s*['\"]DJANGO_SETTINGS_MODULE['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
    content
)
if not m:
    print("")
    raise SystemExit(0)

settings_module = m.group(1).strip()

if ".settings." in settings_module:
    project_module = settings_module.split(".settings.", 1)[0]
    print(f"{project_module}.wsgi:application")
    raise SystemExit(0)
if settings_module.endswith(".settings"):
    project_module = settings_module[: -len(".settings")]
    print(f"{project_module}.wsgi:application")
    raise SystemExit(0)
if "." in settings_module:
    print(f"{settings_module.rsplit('.', 1)[0]}.wsgi:application")
else:
    print(f"{settings_module}.wsgi:application")
PY
}

if [[ "$EUID" -ne 0 ]]; then
  echo "Скрипт должен запускаться от root (через sudo)."
  exit 1
fi

if [[ ! -d "${APP_DIR}" ]]; then
  echo "Каталог ${APP_DIR} не найден. Создайте его и поместите туда код проекта."
  exit 1
fi

if [[ -z "${PROJECT_NAME:-}" ]]; then
  PROJECT_NAME="$(basename "${APP_DIR}")"
fi
read -rp "Имя проекта [${PROJECT_NAME}]: " project_name_input
if [[ -n "${project_name_input}" ]]; then
  PROJECT_NAME="${project_name_input}"
fi
PROJECT_SLUG="$(slugify "${PROJECT_NAME}")"
if [[ -z "${PROJECT_SLUG}" ]]; then
  echo "Не удалось определить PROJECT_NAME. Укажите PROJECT_NAME вручную."
  exit 1
fi

if [[ -z "${DB_NAME:-}" ]]; then
  DB_NAME="${PROJECT_SLUG}"
fi
read -rp "Имя базы данных [${DB_NAME}]: " db_name_input
if [[ -n "${db_name_input}" ]]; then
  DB_NAME="${db_name_input}"
fi

if [[ -z "${DB_USER:-}" ]]; then
  DB_USER="${PROJECT_SLUG}_user"
fi
read -rp "Пользователь базы данных [${DB_USER}]: " db_user_input
if [[ -n "${db_user_input}" ]]; then
  DB_USER="${db_user_input}"
fi

# --- запрос недостающих переменных ---
if [[ -z "${DOMAIN}" ]]; then
  read -rp "Домен или IP сервера (например example.com): " DOMAIN
  if [[ -z "${DOMAIN}" ]]; then
    echo "DOMAIN обязателен. Выход."
    exit 1
  fi
fi

if [[ -z "${DB_PASSWORD}" ]]; then
  read -rsp "Пароль БД для пользователя ${DB_USER}: " DB_PASSWORD
  echo
  if [[ -z "${DB_PASSWORD}" ]]; then
    echo "DB_PASSWORD обязателен. Выход."
    exit 1
  fi
fi

if [[ -z "${DJANGO_SECRET}" ]]; then
  echo "Сгенерировать DJANGO_SECRET_KEY автоматически? (y/n)"
  read -r gen
  if [[ "${gen}" == "y" || "${gen}" == "Y" ]]; then
    DJANGO_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || openssl rand -base64 48)
  else
    read -rsp "Введите DJANGO_SECRET_KEY: " DJANGO_SECRET
    echo
  fi
  if [[ -z "${DJANGO_SECRET}" ]]; then
    echo "DJANGO_SECRET обязателен. Выход."
    exit 1
  fi
fi

if [[ -z "${DJANGO_DIR:-}" ]]; then
  if [[ -f "${APP_DIR}/manage.py" ]]; then
    DJANGO_DIR="."
  elif [[ -f "${APP_DIR}/backend/manage.py" ]]; then
    DJANGO_DIR="backend"
  else
    read -rp "Относительный путь до каталога с manage.py (например backend или .): " DJANGO_DIR
  fi
fi

MANAGE_PY_REL="${DJANGO_DIR}/manage.py"
if [[ ! -f "${APP_DIR}/${MANAGE_PY_REL}" ]]; then
  echo "Не найден manage.py по пути ${APP_DIR}/${MANAGE_PY_REL}."
  echo "Укажите корректный DJANGO_DIR и запустите скрипт снова."
  exit 1
fi

if [[ -z "${REQUIREMENTS_FILE:-}" ]]; then
  if [[ -f "${APP_DIR}/${DJANGO_DIR}/requirements.txt" ]]; then
    REQUIREMENTS_FILE="${DJANGO_DIR}/requirements.txt"
  elif [[ -f "${APP_DIR}/requirements.txt" ]]; then
    REQUIREMENTS_FILE="requirements.txt"
  elif [[ -f "${APP_DIR}/backend/requirements.txt" ]]; then
    REQUIREMENTS_FILE="backend/requirements.txt"
  else
    read -rp "Относительный путь до requirements.txt: " REQUIREMENTS_FILE
  fi
fi

if [[ ! -f "${APP_DIR}/${REQUIREMENTS_FILE}" ]]; then
  echo "Не найден requirements.txt по пути ${APP_DIR}/${REQUIREMENTS_FILE}."
  exit 1
fi

if [[ -z "${WSGI_MODULE:-}" ]]; then
  WSGI_MODULE="$(detect_wsgi_module "${APP_DIR}/${DJANGO_DIR}")"
fi
if [[ -z "${WSGI_MODULE}" ]]; then
  read -rp "WSGI_MODULE (например config.wsgi:application): " WSGI_MODULE
fi
if [[ -z "${WSGI_MODULE}" ]]; then
  echo "WSGI_MODULE обязателен. Выход."
  exit 1
fi

SOCKET_PATH="${APP_DIR}/${PROJECT_SLUG}.sock"
GUNICORN_SERVICE="gunicorn-${PROJECT_SLUG}"
NGINX_SITE="${PROJECT_SLUG}"
STATIC_ROOT="${STATIC_ROOT:-${APP_DIR}/${DJANGO_DIR}/staticfiles}"
MEDIA_ROOT="${MEDIA_ROOT:-${APP_DIR}/${DJANGO_DIR}/media}"
ORIGIN="${APP_SCHEME}://${DOMAIN}"

if [[ -z "${FRONTEND_DIR:-}" ]]; then
  if [[ -f "${APP_DIR}/frontend/package.json" ]]; then
    FRONTEND_DIR="frontend"
  fi
fi

ENABLE_FRONTEND="false"
if [[ -n "${FRONTEND_DIR:-}" && -f "${APP_DIR}/${FRONTEND_DIR}/package.json" ]]; then
  ENABLE_FRONTEND="true"
fi

if [[ "${ENABLE_FRONTEND}" == "true" ]]; then
  FRONTEND_BUILD_DIR="${FRONTEND_BUILD_DIR:-${APP_DIR}/${FRONTEND_DIR}/dist}"
fi

echo "Настройка:"
echo "  PROJECT_NAME=${PROJECT_NAME}"
echo "  APP_DIR=${APP_DIR}"
echo "  DOMAIN=${DOMAIN}"
echo "  ORIGIN=${ORIGIN}"
echo "  DJANGO_DIR=${DJANGO_DIR}"
echo "  MANAGE_PY=${MANAGE_PY_REL}"
echo "  REQUIREMENTS_FILE=${REQUIREMENTS_FILE}"
echo "  WSGI_MODULE=${WSGI_MODULE}"
echo "  DB_NAME=${DB_NAME}"
echo "  DB_USER=${DB_USER}"
if [[ "${ENABLE_FRONTEND}" == "true" ]]; then
  echo "  FRONTEND_DIR=${FRONTEND_DIR}"
  echo "  FRONTEND_BUILD_DIR=${FRONTEND_BUILD_DIR}"
else
  echo "  FRONTEND=disabled"
fi

# --- 1. Система и пакеты ---
echo "[1/7] Обновление системы и установка пакетов..."
apt_get_install() {
  local packages=("$@")
  if ! apt-get install -y "${packages[@]}"; then
    echo "Ошибка установки пакетов: ${packages[*]}"
    echo "Пробуем восстановить состояние APT (dpkg --configure -a, apt-get -f install)..."
    dpkg --configure -a || true
    apt-get -f install -y || true
    if ! apt-get install -y "${packages[@]}"; then
      echo "Не удалось установить пакеты после восстановления."
      held_packages="$(apt-mark showhold || true)"
      if [[ -n "${held_packages}" ]]; then
        echo "Обнаружены удерживаемые пакеты (hold):"
        echo "${held_packages}"
        echo "Снимите hold при необходимости (пример): apt-mark unhold <package>"
      fi
      exit 1
    fi
  fi
}

apt-get update
apt-get upgrade -y

base_packages=(
  python3
  python3-pip
  python3-venv
  nginx
  postgresql
  postgresql-contrib
)
apt_get_install "${base_packages[@]}"

if [[ "${ENABLE_FRONTEND}" == "true" ]]; then
  echo "Обнаружен frontend: устанавливаю nodejs и npm..."
  apt_get_install nodejs npm
else
  echo "Frontend отключен: nodejs и npm не устанавливаются."
fi

# --- 2. PostgreSQL ---
echo "[2/7] Настройка PostgreSQL..."
sudo -u postgres psql -v ON_ERROR_STOP=1 <<EOF
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
  ELSE
    ALTER USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
  END IF;
END \$\$;
ALTER ROLE ${DB_USER} SET client_encoding TO 'utf8';
ALTER ROLE ${DB_USER} SET default_transaction_isolation TO 'read committed';
ALTER ROLE ${DB_USER} SET timezone TO 'Europe/Moscow';
EOF
if ! sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw "${DB_NAME}"; then
  sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"
fi
sudo -u postgres psql -d "${DB_NAME}" -v ON_ERROR_STOP=1 -c "GRANT ALL ON SCHEMA public TO ${DB_USER};"

# --- 3. Каталог приложения ---
echo "[3/7] Подготовка каталога приложения..."
cd "${APP_DIR}"

# .env
if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    cp .env.example .env
  else
    touch .env
  fi
fi

# подстановка переменных в .env (безопасно для спецсимволов, сохраняет порядок и комментарии)
set_env_var() {
  local key="$1"
  local value="$2"
  export SETENV_KEY="$key"
  export SETENV_VAL="$value"
  python3 -c "
import os
path = '.env'
key = os.environ['SETENV_KEY']
val = os.environ['SETENV_VAL']
lines = []
done = set()
if os.path.exists(path):
    with open(path) as f:
        for line in f:
            s = line.rstrip('\n')
            if s.strip() and '=' in s and not s.strip().startswith('#'):
                k, _, v = s.partition('=')
                k = k.strip()
                if k == key:
                    lines.append(f'{k}={val}\n')
                    done.add(key)
                    continue
            lines.append(line if line.endswith('\n') else line + '\n')
if key not in done:
    lines.append(f'{key}={val}\n')
with open(path, 'w') as f:
    f.writelines(lines)
"
}

# Основные переменные, которые читает текущий settings/base.py
set_env_var "DB_NAME" "${DB_NAME}"
set_env_var "DB_USER" "${DB_USER}"
set_env_var "DB_PASSWORD" "${DB_PASSWORD}"
set_env_var "DB_HOST" "${DB_HOST}"
set_env_var "DB_PORT" "${DB_PORT}"
set_env_var "SECRET_KEY" "${DJANGO_SECRET}"
set_env_var "DEBUG" "False"
set_env_var "ALLOWED_HOSTS" "127.0.0.1,localhost,${DOMAIN}"
set_env_var "CSRF_TRUSTED_ORIGINS" "${ORIGIN}"

# Обратная совместимость со старыми именами переменных
set_env_var "POSTGRES_DB" "${DB_NAME}"
set_env_var "POSTGRES_USER" "${DB_USER}"
set_env_var "POSTGRES_PASSWORD" "${DB_PASSWORD}"
set_env_var "POSTGRES_HOST" "${DB_HOST}"
set_env_var "POSTGRES_PORT" "${DB_PORT}"
set_env_var "DJANGO_SECRET_KEY" "${DJANGO_SECRET}"
set_env_var "DJANGO_DEBUG" "False"
set_env_var "DJANGO_ALLOWED_HOSTS" "127.0.0.1,localhost,${DOMAIN}"
set_env_var "DJANGO_CSRF_TRUSTED_ORIGINS" "${ORIGIN}"

# venv и зависимости
if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r "${REQUIREMENTS_FILE}"
.venv/bin/pip install -q gunicorn

# Django logging может писать в BASE_DIR/logs/django.log.
# Создаём каталог заранее, чтобы migrate/collectstatic не падали.
mkdir -p "${APP_DIR}/${DJANGO_DIR}/logs"
mkdir -p "${MEDIA_ROOT}"

# миграции и статика
.venv/bin/python "${MANAGE_PY_REL}" migrate --noinput
.venv/bin/python "${MANAGE_PY_REL}" collectstatic --noinput --clear

# фронтенд (опционально): сборка для Nginx
if [[ "${ENABLE_FRONTEND}" == "true" ]]; then
  echo "[4/8] Сборка frontend..."
  if [[ -f "${APP_DIR}/${FRONTEND_DIR}/package-lock.json" ]]; then
    npm --prefix "${APP_DIR}/${FRONTEND_DIR}" ci
  else
    npm --prefix "${APP_DIR}/${FRONTEND_DIR}" install
  fi
  npm --prefix "${APP_DIR}/${FRONTEND_DIR}" run build

  if [[ ! -f "${FRONTEND_BUILD_DIR}/index.html" ]]; then
    echo "Не найден собранный frontend: ${FRONTEND_BUILD_DIR}/index.html"
    exit 1
  fi
fi

# владелец — сервисный пользователь
chown -R ${SERVICE_USER}:${SERVICE_USER} "${APP_DIR}"

# --- 4. Gunicorn (systemd) ---
echo "[5/8] Установка сервиса Gunicorn..."
cat > "/etc/systemd/system/${GUNICORN_SERVICE}.service" <<GUNICORN
[Unit]
Description=Gunicorn daemon for ${PROJECT_NAME}
After=network.target postgresql.service

[Service]
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${APP_DIR}/${DJANGO_DIR}
ExecStart=${APP_DIR}/.venv/bin/gunicorn \\
    --workers ${GUNICORN_WORKERS} \\
    --bind unix:${SOCKET_PATH} \\
    --timeout ${GUNICORN_TIMEOUT} \\
    ${WSGI_MODULE}
Restart=always
RestartSec=5
EnvironmentFile=${APP_DIR}/.env

[Install]
WantedBy=multi-user.target
GUNICORN

systemctl daemon-reload
systemctl enable "${GUNICORN_SERVICE}"
systemctl restart "${GUNICORN_SERVICE}"

# --- 6. Nginx ---
echo "[6/8] Настройка Nginx..."
if ! command -v nginx >/dev/null 2>&1; then
  echo "Nginx не найден в системе (команда nginx отсутствует)."
  echo "Проверьте установку пакета nginx и запустите скрипт снова."
  exit 1
fi

NGINX_AVAILABLE_DIR="/etc/nginx/sites-available"
NGINX_ENABLED_DIR="/etc/nginx/sites-enabled"
mkdir -p "${NGINX_AVAILABLE_DIR}" "${NGINX_ENABLED_DIR}"

if [[ "${ENABLE_FRONTEND}" == "true" ]]; then
cat > "${NGINX_AVAILABLE_DIR}/${NGINX_SITE}" <<NGINX
server {
    listen 80;
    server_name ${DOMAIN};

    client_max_body_size 50M;

    location /static/ {
        alias ${STATIC_ROOT}/;
    }

    location /media/ {
        alias ${MEDIA_ROOT}/;
    }

    location /api/ {
        proxy_pass http://unix:${SOCKET_PATH};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 120s;
        proxy_read_timeout 120s;
    }

    location /admin/ {
        proxy_pass http://unix:${SOCKET_PATH};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 120s;
        proxy_read_timeout 120s;
    }

    location /assets/ {
        alias ${FRONTEND_BUILD_DIR}/assets/;
        access_log off;
        expires 30d;
    }

    location = /favicon.ico {
        alias ${FRONTEND_BUILD_DIR}/favicon.ico;
        access_log off;
        log_not_found off;
    }

    location / {
        root ${FRONTEND_BUILD_DIR};
        try_files \$uri /index.html;
    }
}
NGINX
else
cat > "${NGINX_AVAILABLE_DIR}/${NGINX_SITE}" <<NGINX
server {
    listen 80;
    server_name ${DOMAIN};

    client_max_body_size 50M;

    location /static/ {
        alias ${STATIC_ROOT}/;
    }

    location /media/ {
        alias ${MEDIA_ROOT}/;
    }

    location / {
        proxy_pass http://unix:${SOCKET_PATH};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 120s;
        proxy_read_timeout 120s;
    }
}
NGINX
fi

ln -sf "${NGINX_AVAILABLE_DIR}/${NGINX_SITE}" "${NGINX_ENABLED_DIR}/${NGINX_SITE}"
nginx -t && systemctl reload nginx

# --- 7. Суперпользователь (опционально) ---
echo "[7/8] Суперпользователь Django (опционально)."
echo "Создайте вручную, если нужно:"
echo "  cd ${APP_DIR} && .venv/bin/python ${MANAGE_PY_REL} createsuperuser"

# --- 8. Итог ---
echo "[8/8] Готово."
echo ""
echo "  Приложение:  ${ORIGIN}"
echo "  Статика:     ${STATIC_ROOT}/"
echo "  Медиа:       ${MEDIA_ROOT}/"
echo "  Gunicorn:    ${GUNICORN_SERVICE}.service"
echo "  Nginx site:  ${NGINX_SITE}"
if [[ "${ENABLE_FRONTEND}" == "true" ]]; then
  echo "  Frontend:    ${FRONTEND_BUILD_DIR}"
fi
echo "  Логи:        journalctl -u ${GUNICORN_SERVICE} -f"
echo ""
