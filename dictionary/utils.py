import ipaddress

from django.conf import settings


def client_ip(request):
    """
    IP посетителя. За обратным прокси (Caddy/nginx) берём последний адрес из
    X-Forwarded-For — его дописывает наш прокси, подделать его клиент не может.
    Эту же функцию использует django-axes (AXES_CLIENT_IP_CALLABLE).
    """
    ip = request.META.get("REMOTE_ADDR", "")
    if settings.BEHIND_PROXY:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            ip = forwarded.split(",")[-1].strip()
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return "0.0.0.0"
