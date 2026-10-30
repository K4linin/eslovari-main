#!/bin/sh
# Резервная копия базы и загруженных файлов. Запуск из папки проекта:
#   sh deploy/backup.sh
# Для ежедневного запуска добавьте в crontab (crontab -e):
#   30 3 * * * cd /opt/eslovari && sh deploy/backup.sh >> /var/log/eslovari-backup.log 2>&1
set -e
cd "$(dirname "$0")/.."
# Читаем из .env только нужные значения (сам файл не выполняем)
env_value() { grep -E "^$1=" .env | tail -n1 | cut -d= -f2-; }
DB_USER=$(env_value DB_USER)
DB_NAME=$(env_value DB_NAME)
STAMP=$(date +%Y-%m-%d_%H-%M)
DIR=backups
mkdir -p "$DIR"
COMPOSE="docker compose -f docker-compose.prod.yml"

$COMPOSE exec -T db pg_dump -U "${DB_USER:-eslovari}" -d "${DB_NAME:-eslovari}" --clean --if-exists \
  | gzip > "$DIR/db_$STAMP.sql.gz"
$COMPOSE exec -T web tar -czf - -C /app media > "$DIR/media_$STAMP.tar.gz"

# Храним копии за последние 14 дней
find "$DIR" -type f -mtime +14 -delete
echo "$(date) backup ok: $DIR/db_$STAMP.sql.gz"
