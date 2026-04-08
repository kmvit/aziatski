# Скрипты развёртывания

## setup-server.sh

Универсально настраивает Ubuntu под любой Django-проект:

- обновление системы, установка nginx, PostgreSQL, Python3/venv
- создание БД и пользователя PostgreSQL
- разворот приложения в `APP_DIR`: venv, зависимости, миграции, статика
- сервис Gunicorn (`gunicorn-<project_name>.service`)
- конфиг Nginx (`/etc/nginx/sites-available/<project_name>`)

**Использование на сервере:**

1. Склонируйте или скопируйте Django-проект в `APP_DIR` (по умолчанию `/opt/django_project`).
   Скрипт автоматически ищет `manage.py` в корне и в `backend/`, либо запросит путь вручную.

2. Запустите скрипт от root:
   ```bash
   sudo bash scripts/setup-server.sh
   ```

3. Скрипт запросит (или возьмёт из переменных окружения):
   - **Домен или IP** — например `4771a76b3f3c.vps.myjino.ru`
   - **Имя проекта** — для именования systemd/nginx/сокета
   - **Имя БД**
   - **Пользователь БД**
   - **Пароль БД**
   - **DJANGO_SECRET_KEY** — сгенерировать автоматически или ввести вручную
   - при необходимости: путь до `manage.py`, путь до `requirements.txt`, `WSGI_MODULE`

**Переменные окружения (опционально):**

```bash
export APP_DIR=/opt/my_django_project
export PROJECT_NAME=my_django_project
export DOMAIN=4771a76b3f3c.vps.myjino.ru
export APP_SCHEME=https

export DB_NAME=my_django_project
export DB_USER=my_django_project_user
export DB_PASSWORD=надёжный_пароль
export DB_HOST=localhost
export DB_PORT=5432

export DJANGO_SECRET=ваш_секрет_или_оставьте_пустым_для_автогенерации
export DJANGO_DIR=backend
export REQUIREMENTS_FILE=backend/requirements.txt
export WSGI_MODULE=config.wsgi:application
export STATIC_ROOT=/opt/my_django_project/backend/staticfiles

sudo -E bash scripts/setup-server.sh
```

После установки при необходимости создайте администратора вручную:

```bash
cd "$APP_DIR"
.venv/bin/python "$DJANGO_DIR/manage.py" createsuperuser
```
