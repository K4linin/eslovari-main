from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from dictionary import admin_site  # noqa: F401  (подключает вход в админку через сайт)

admin.site.site_header = "eSlovari — панель наполнения"
admin.site.site_title = "eSlovari"
admin.site.index_title = "Словарь, наборы и статьи"

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    # Наши адреса — раньше social: иначе /login/2fa/ попадёт в social «login/<backend>/»
    path("", include("dictionary.urls")),
    path("", include("social_django.urls", namespace="social")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "dictionary.views.page_not_found"
handler500 = "dictionary.views.server_error"
