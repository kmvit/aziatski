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
#   APP_DIR           — каталог приложения (по умолчанию /opt/django_project)
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
#
set -e

APP_DIR="${APP_DIR:-/opt/django_project}"
SERVICE_USER="${SERVICE_USER:-www-data}"
APP_SCHEME="${APP_SCHEME:-https}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-3}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"

slugify() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]' '_' | sed 's/^_//; s/_$//'
}

detect_wsgi_module() {
  local manage_py="$1/manage.py"
  python3 - "$manage_py" <<'PY'
import re
import sys

path = sys.argv[1]
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
if "." in settings_module:
    base_module = settings_module.rsplit(".", 1)[0]
else:
    base_module = settings_module

print(f"{base_module}.wsgi:application")
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
ORIGIN="${APP_SCHEME}://${DOMAIN}"

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

# --- 1. Система и пакеты ---
echo "[1/7] Обновление системы и установка пакетов..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq python3 python3-pip python3-venv nginx postgresql postgresql-contrib

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

# миграции и статика
.venv/bin/python "${MANAGE_PY_REL}" migrate --noinput
.venv/bin/python "${MANAGE_PY_REL}" collectstatic --noinput --clear

# владелец — сервисный пользователь
chown -R ${SERVICE_USER}:${SERVICE_USER} "${APP_DIR}"

# --- 4. Gunicorn (systemd) ---
echo "[4/7] Установка сервиса Gunicorn..."
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

# --- 5. Nginx ---
echo "[5/7] Настройка Nginx..."
cat > "/etc/nginx/sites-available/${NGINX_SITE}" <<NGINX
server {
    listen 80;
    server_name ${DOMAIN};

    client_max_body_size 50M;

    location /static/ {
        alias ${STATIC_ROOT}/;
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

ln -sf "/etc/nginx/sites-available/${NGINX_SITE}" "/etc/nginx/sites-enabled/${NGINX_SITE}"
nginx -t && systemctl reload nginx

# --- 6. Суперпользователь (опционально) ---
echo "[6/7] Суперпользователь Django (опционально)."
echo "Создайте вручную, если нужно:"
echo "  cd ${APP_DIR} && .venv/bin/python ${MANAGE_PY_REL} createsuperuser"

# --- 7. Итог ---
echo "[7/7] Готово."
echo ""
echo "  Приложение:  ${ORIGIN}"
echo "  Статика:     ${STATIC_ROOT}/"
echo "  Gunicorn:    ${GUNICORN_SERVICE}.service"
echo "  Nginx site:  ${NGINX_SITE}"
echo "  Логи:        journalctl -u ${GUNICORN_SERVICE} -f"
echo ""
