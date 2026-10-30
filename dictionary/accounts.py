"""Регистрация, вход (с 2FA), управление двухфакторной аутентификацией."""
import base64
import time
from base64 import b32encode
from datetime import timedelta

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST
from django_otp import devices_for_user, user_has_device
from django_otp import login as otp_login
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from .forms import (
    LoginForm,
    OTPTokenForm,
    PasswordConfirmForm,
    SignupForm,
    TOTPConfirmForm,
)
from .models import SignupLog
from .utils import client_ip

User = get_user_model()

PENDING_KEY = "otp_pending"
PENDING_TTL = 5 * 60  # на ввод кода даётся 5 минут
PENDING_MAX_TRIES = 5
BACKUP_CODES_COUNT = 8


def apply_remember_me(request, remember):
    # 0 — сессия живёт до закрытия браузера, None — SESSION_COOKIE_AGE (30 дней)
    request.session.set_expiry(None if remember else 0)


class SiteLoginView(LoginView):
    """Шаг 1: логин и пароль. Если у пользователя включена 2FA — шаг 2."""

    form_class = LoginForm
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        remember = form.cleaned_data.get("remember_me", False)
        if user_has_device(user, confirmed=True):
            self.request.session[PENDING_KEY] = {
                "uid": user.pk,
                "backend": user.backend,
                "remember": remember,
                "next": self.get_success_url(),
                "ts": time.time(),
                "tries": 0,
            }
            return redirect("login_2fa")
        auth_login(self.request, user)
        apply_remember_me(self.request, remember)
        return redirect(self.get_success_url())


@never_cache
@sensitive_post_parameters("token")
def login_2fa(request):
    """Шаг 2: код из приложения-аутентификатора или резервный код."""
    pending = request.session.get(PENDING_KEY)
    if not pending or time.time() - pending["ts"] > PENDING_TTL:
        request.session.pop(PENDING_KEY, None)
        messages.warning(request, "Время на ввод кода истекло — войдите ещё раз.")
        return redirect("login")

    user = User.objects.filter(pk=pending["uid"], is_active=True).first()
    if user is None:
        request.session.pop(PENDING_KEY, None)
        return redirect("login")

    form = OTPTokenForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        device = verify_user_token(user, form.cleaned_data["token"])
        if device is not None:
            request.session.pop(PENDING_KEY, None)
            auth_login(request, user, backend=pending["backend"])
            otp_login(request, device)
            apply_remember_me(request, pending["remember"])
            if isinstance(device, StaticDevice):
                left = device.token_set.count()
                messages.warning(
                    request,
                    f"Вы вошли по резервному коду. Осталось кодов: {left}. "
                    "Создайте новые в профиле, если их мало.",
                )
            return redirect(pending["next"])

        pending["tries"] += 1
        if pending["tries"] >= PENDING_MAX_TRIES:
            request.session.pop(PENDING_KEY, None)
            messages.error(request, "Слишком много неверных кодов. Войдите заново.")
            return redirect("login")
        request.session[PENDING_KEY] = pending
        form.add_error("token", "Неверный код. Проверьте время на телефоне и попробуйте снова.")

    return render(request, "registration/login_2fa.html", {"form": form})


def verify_user_token(user, token):
    """6 цифр — проверяем приложение (TOTP), иначе — резервные коды."""
    if token.isdigit() and len(token) == 6:
        candidates = TOTPDevice.objects.devices_for_user(user, confirmed=True)
    else:
        token = token.lower()
        candidates = StaticDevice.objects.devices_for_user(user, confirmed=True)
    with transaction.atomic():
        for device in candidates:
            if device.verify_is_allowed()[0] and device.verify_token(token):
                return device
    return None


@never_cache
@sensitive_post_parameters("password1", "password2")
def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = SignupForm(request.POST or None)
    status = 200
    if request.method == "POST":
        ip = client_ip(request)
        hour_ago = timezone.now() - timedelta(hours=1)
        SignupLog.objects.filter(created_at__lt=timezone.now() - timedelta(days=1)).delete()
        if SignupLog.objects.filter(ip=ip, created_at__gte=hour_ago).count() >= settings.SIGNUP_LIMIT_PER_HOUR:
            form.add_error(None, "С вашего адреса уже было много регистраций. Попробуйте через час.")
            status = 429
        elif form.is_valid():
            user = form.save()
            SignupLog.objects.create(ip=ip)
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            apply_remember_me(request, False)
            messages.success(request, f"Добро пожаловать, {user.username}! Аккаунт создан.")
            return redirect("home")
    return render(request, "registration/register.html", {"form": form}, status=status)


# --- Управление 2FA в профиле ----------------------------------------------------


def _qr_data_uri(url):
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    return "data:image/svg+xml;base64," + base64.b64encode(img.to_string()).decode()


def _new_backup_codes(user):
    device, _ = StaticDevice.objects.get_or_create(
        user=user, name="Резервные коды", defaults={"confirmed": True}
    )
    device.token_set.all().delete()
    codes = [StaticToken.random_token() for _ in range(BACKUP_CODES_COUNT)]
    StaticToken.objects.bulk_create(StaticToken(device=device, token=c) for c in codes)
    return codes


@login_required
@never_cache
def twofa_setup(request):
    user = request.user
    if not user.has_usable_password():
        messages.info(request, "Вы входите через Яндекс — второй фактор обеспечивает Яндекс ID.")
        return redirect("profile")
    if TOTPDevice.objects.filter(user=user, confirmed=True).exists():
        messages.info(request, "Двухфакторная аутентификация уже включена.")
        return redirect("profile")

    device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
    if device is None:
        device = TOTPDevice.objects.create(user=user, name="Приложение", confirmed=False)

    form = TOTPConfirmForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if device.verify_token(form.cleaned_data["token"]):
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            otp_login(request, device)
            request.session["backup_codes"] = _new_backup_codes(user)
            messages.success(request, "2FA включена! Сохраните резервные коды.")
            return redirect("twofa_backup_codes")
        form.add_error("token", "Код не подошёл. Проверьте, что время на телефоне точное.")

    secret = b32encode(device.bin_key).decode()
    return render(
        request,
        "dictionary/twofa_setup.html",
        {
            "form": form,
            "qr": _qr_data_uri(device.config_url),
            "otpauth_url": device.config_url,
            "secret": " ".join(secret[i : i + 4] for i in range(0, len(secret), 4)),
        },
    )


@login_required
@never_cache
def twofa_backup_codes(request):
    """Показывает резервные коды один раз сразу после создания."""
    codes = request.session.pop("backup_codes", None)
    if not codes:
        return redirect("profile")
    return render(request, "dictionary/twofa_codes.html", {"codes": codes})


@login_required
@require_POST
@sensitive_post_parameters("password")
def twofa_regenerate(request):
    form = PasswordConfirmForm(request.user, request.POST)
    if not user_has_device(request.user) or not form.is_valid():
        messages.error(request, "Неверный пароль — коды не изменены.")
        return redirect("profile")
    request.session["backup_codes"] = _new_backup_codes(request.user)
    messages.success(request, "Созданы новые резервные коды. Старые больше не работают.")
    return redirect("twofa_backup_codes")


@login_required
@require_POST
@sensitive_post_parameters("password")
def twofa_disable(request):
    form = PasswordConfirmForm(request.user, request.POST)
    if not form.is_valid():
        messages.error(request, "Неверный пароль — 2FA осталась включённой.")
        return redirect("profile")
    for device in devices_for_user(request.user, confirmed=None):
        device.delete()
    messages.success(request, "Двухфакторная аутентификация отключена.")
    return redirect("profile")
