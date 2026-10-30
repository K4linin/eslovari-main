"""
Вход в админку — только через общий защищённый вход сайта (django-axes + 2FA).
Своей формы пароля у админки нет: её login() перенаправляет на /login/.
"""
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

_default_has_permission = admin.site.has_permission


def has_permission(request):
    if not _default_has_permission(request):
        return False
    if settings.ADMIN_REQUIRE_2FA:
        return request.user.is_verified()
    return True


def admin_login(request, extra_context=None):
    next_url = request.GET.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = reverse("admin:index")

    if not request.user.is_authenticated:
        return redirect_to_login(next_url, login_url=reverse("login"))
    if not request.user.is_staff:
        raise PermissionDenied("Панель наполнения доступна только сотрудникам.")
    if settings.ADMIN_REQUIRE_2FA and not request.user.is_verified():
        messages.warning(
            request,
            "Для входа в панель наполнения включите двухфакторную аутентификацию "
            "и войдите заново с кодом из приложения.",
        )
        return redirect("profile")
    return redirect(next_url)


admin.site.has_permission = has_permission
admin.site.login = admin_login
