"""
Настройки проекта eslovari.ru.

Всё, что отличается между компьютером разработчика и сервером, читается
из файла .env (см. .env.example). В репозиторий .env не попадает.
"""
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Основное -----------------------------------------------------------------

SECRET_KEY = config("SECRET_KEY", default="dev-insecure-key-change-me")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=Csv())
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())

if not DEBUG and (len(SECRET_KEY) < 40 or SECRET_KEY.startswith("dev-insecure")):
    raise RuntimeError(
        "SECRET_KEY не задан. Пропишите длинный случайный SECRET_KEY в .env "
        "(или включите DEBUG=True для локальной разработки)."
    )

# Адрес админки можно спрятать от сканеров: ADMIN_URL=secret-panel-42
ADMIN_URL = config("ADMIN_URL", default="admin").strip("/") + "/"
# Требовать подтверждённую 2FA для входа сотрудников в админку
ADMIN_REQUIRE_2FA = config("ADMIN_REQUIRE_2FA", default=False, cast=bool)

SITE_NAME = "eSlovari"
SITE_DOMAIN = config("SITE_DOMAIN", default="eslovari.ru")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "axes",
    "social_django",
    "dictionary",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "dictionary.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "social_django.middleware.SocialAuthExceptionMiddleware",
    # AxesMiddleware должен быть последним
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "electronic_dictionary.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "social_django.context_processors.backends",
                "dictionary.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "electronic_dictionary.wsgi.application"

# --- База данных ----------------------------------------------------------------
# По умолчанию SQLite (ничего настраивать не нужно). Для сервера — PostgreSQL:
# DB_ENGINE=postgresql и DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT в .env.

if config("DB_ENGINE", default="sqlite") == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="eslovari"),
            "USER": config("DB_USER", default="eslovari"),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Пароли и вход --------------------------------------------------------------

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    # Остальные — только чтобы проверить старые хэши; новые пишутся Argon2
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "dictionary.validators.LettersAndDigitsValidator"},
]

AUTHENTICATION_BACKENDS = [
    # AxesStandaloneBackend должен идти первым — он блокирует перебор паролей
    "axes.backends.AxesStandaloneBackend",
    "social_core.backends.yandex.YandexOAuth2",
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

# Регистрация: не больше N аккаунтов с одного IP за час
SIGNUP_LIMIT_PER_HOUR = config("SIGNUP_LIMIT_PER_HOUR", default=5, cast=int)
# Минимальное время заполнения формы регистрации (секунды) — отсекает ботов
SIGNUP_MIN_SECONDS = config("SIGNUP_MIN_SECONDS", default=3, cast=int)

# «Запомнить меня» — 30 дней; без галочки сессия до закрытия браузера
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True

# --- django-axes: защита от подбора пароля --------------------------------------

AXES_FAILURE_LIMIT = config("AXES_FAILURE_LIMIT", default=5, cast=int)
AXES_COOLOFF_TIME = config("AXES_COOLOFF_HOURS", default=1, cast=float)
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "registration/lockout.html"
AXES_USERNAME_FORM_FIELD = "username"
# За обратным прокси (Caddy/nginx) настоящий IP приходит в X-Forwarded-For
BEHIND_PROXY = config("BEHIND_PROXY", default=False, cast=bool)
AXES_CLIENT_IP_CALLABLE = "dictionary.utils.client_ip"

# --- django-otp: двухфакторная аутентификация -----------------------------------

OTP_TOTP_ISSUER = SITE_DOMAIN
OTP_TOTP_THROTTLE_FACTOR = 1

# --- Вход через Яндекс (social-auth) --------------------------------------------

SOCIAL_AUTH_YANDEX_OAUTH2_KEY = config("YANDEX_CLIENT_ID", default="")
SOCIAL_AUTH_YANDEX_OAUTH2_SECRET = config("YANDEX_CLIENT_SECRET", default="")
YANDEX_LOGIN_ENABLED = bool(SOCIAL_AUTH_YANDEX_OAUTH2_KEY and SOCIAL_AUTH_YANDEX_OAUTH2_SECRET)
SOCIAL_AUTH_URL_NAMESPACE = "social"
SOCIAL_AUTH_LOGIN_ERROR_URL = "/login/"
SOCIAL_AUTH_REDIRECT_IS_HTTPS = config("SOCIAL_AUTH_REDIRECT_IS_HTTPS", default=not DEBUG, cast=bool)
SOCIAL_AUTH_JSONFIELD_ENABLED = True
SOCIAL_AUTH_PIPELINE = (
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
    "social_core.pipeline.social_auth.social_user",
    "social_core.pipeline.user.get_username",
    # Связываем с существующим аккаунтом по подтверждённому Яндексом email
    "social_core.pipeline.social_auth.associate_by_email",
    "social_core.pipeline.user.create_user",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.social_auth.load_extra_data",
    "social_core.pipeline.user.user_details",
)

# --- Почта (восстановление пароля) ----------------------------------------------

EMAIL_BACKEND = config(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=465, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=True, cast=bool)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=False, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="eSlovari <noreply@eslovari.ru>")
PASSWORD_RESET_TIMEOUT = 60 * 60 * 2  # ссылка действует 2 часа

# --- Язык и время -----------------------------------------------------------------

LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

# --- Статика и загружаемые файлы ------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

MEDIA_URL = "media/"
MEDIA_ROOT = config("MEDIA_ROOT", default=str(BASE_DIR / "media"))

# Ограничения на загрузку: аватар до 2 МБ, Excel до 5 МБ
AVATAR_MAX_BYTES = 2 * 1024 * 1024
EXCEL_MAX_BYTES = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

# --- Заголовки безопасности -------------------------------------------------------

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
    SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False
    SESSION_COOKIE_NAME = "__Host-sessionid"
    CSRF_COOKIE_NAME = "__Host-csrftoken"

# Content-Security-Policy: скрипты только с нашего домена, никаких inline-скриптов
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https://avatars.yandex.net; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self' https://oauth.yandex.ru; "
    "base-uri 'self'; "
    "object-src 'none'"
)

# --- Логи -------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "axes": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
