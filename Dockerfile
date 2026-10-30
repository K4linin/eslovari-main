FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Собираем статику на этапе сборки образа (ключ здесь временный, в работе не используется)
RUN SECRET_KEY=build-only-not-secret-$(date +%s)-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx DEBUG=False \
    python manage.py collectstatic --noinput \
 && useradd --system --uid 1000 --home /app app \
 && mkdir -p /app/media \
 && chown -R app:app /app/media \
 && chmod +x deploy/entrypoint.sh

# Сайт работает не от root — так взлом приложения не даёт прав на контейнер
USER app

EXPOSE 8000
ENTRYPOINT ["deploy/entrypoint.sh"]
CMD ["gunicorn", "electronic_dictionary.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", "--access-logfile", "-"]
