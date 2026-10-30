#!/bin/sh
# Перед запуском сайта применяем миграции базы данных
set -e
python manage.py migrate --noinput
exec "$@"
