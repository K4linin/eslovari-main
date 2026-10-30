import re

from django.core.exceptions import ValidationError

# Имена, которые нельзя занять при регистрации — чтобы никто не выдавал себя
# за администрацию сайта.
RESERVED_USERNAMES = {
    "admin", "administrator", "administrador", "root", "superuser", "support",
    "help", "helpdesk", "moderator", "mod", "staff", "system", "sysadmin",
    "owner", "webmaster", "postmaster", "hostmaster", "info", "security",
    "abuse", "noreply", "no-reply", "mail", "api", "www", "eslovari", "official",
    "админ", "администратор", "модератор", "поддержка",
}


def validate_username_not_reserved(value):
    normalized = re.sub(r"[\W_]+", "", value.lower())
    if value.lower() in RESERVED_USERNAMES or normalized in RESERVED_USERNAMES:
        raise ValidationError("Это имя зарезервировано. Выберите другое.")


class LettersAndDigitsValidator:
    """Пароль должен содержать хотя бы одну букву и хотя бы одну цифру."""

    def validate(self, password, user=None):
        if not re.search(r"[^\W\d_]", password) or not re.search(r"\d", password):
            raise ValidationError(
                "Пароль должен содержать и буквы, и цифры.",
                code="password_letters_digits",
            )

    def get_help_text(self):
        return "Пароль должен содержать и буквы, и цифры."
