from django.conf import settings


def site(request):
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_DOMAIN": settings.SITE_DOMAIN,
        "YANDEX_LOGIN_ENABLED": settings.YANDEX_LOGIN_ENABLED,
        "ADMIN_URL": "/" + settings.ADMIN_URL,
    }
