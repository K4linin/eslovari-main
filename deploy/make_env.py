"""Создаёт .env из .env.example и вписывает случайный SECRET_KEY (и пароль БД)."""
import re
import secrets
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
env = root / ".env"
if env.exists():
    print(".env уже существует — не трогаю.")
    sys.exit(0)

text = (root / ".env.example").read_text(encoding="utf-8")
text = re.sub(r"(?m)^SECRET_KEY=.*$", "SECRET_KEY=" + secrets.token_urlsafe(50), text)
if "--server" in sys.argv:
    text = re.sub(r"(?m)^DEBUG=.*$", "DEBUG=False", text)
    text = re.sub(r"(?m)^DB_PASSWORD=.*$", "DB_PASSWORD=" + secrets.token_urlsafe(24), text)
    text = re.sub(r"(?m)^DB_ENGINE=.*$", "DB_ENGINE=postgresql", text)
    text = re.sub(r"(?m)^ADMIN_URL=.*$", "ADMIN_URL=panel-" + secrets.token_hex(4), text)
    text = re.sub(r"(?m)^ADMIN_REQUIRE_2FA=.*$", "ADMIN_REQUIRE_2FA=True", text)
env.write_text(text, encoding="utf-8")
print("Создан .env со случайным SECRET_KEY.")
