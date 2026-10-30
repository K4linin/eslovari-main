from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import accounts, views

urlpatterns = [
    path("", views.home, name="home"),
    path("word/<int:pk>/", views.entry_detail, name="entry_detail"),
    path("word/<int:pk>/to-topic/", views.topic_add_entry, name="topic_add_entry"),
    path("sets/", views.set_list, name="set_list"),
    path("sets/<slug:slug>/", views.set_detail, name="set_detail"),
    path("trainer/", views.trainer, name="trainer"),
    path("trainer/result/", views.trainer_result, name="trainer_result"),
    path("my/", views.topic_list, name="topic_list"),
    path("my/<int:pk>/", views.topic_detail, name="topic_detail"),
    path("articles/", views.article_list, name="article_list"),
    path("articles/<slug:slug>/", views.article_detail, name="article_detail"),
    path("favorites/", views.favorites, name="favorites"),
    path("fav/<str:kind>/<int:pk>/", views.toggle_favorite, name="toggle_favorite"),
    path("profile/", views.profile, name="profile"),
    # Вход, регистрация, 2FA
    path("login/", accounts.SiteLoginView.as_view(), name="login"),
    path("login/2fa/", accounts.login_2fa, name="login_2fa"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", accounts.register, name="register"),
    path("profile/2fa/", accounts.twofa_setup, name="twofa_setup"),
    path("profile/2fa/codes/", accounts.twofa_backup_codes, name="twofa_backup_codes"),
    path("profile/2fa/regenerate/", accounts.twofa_regenerate, name="twofa_regenerate"),
    path("profile/2fa/disable/", accounts.twofa_disable, name="twofa_disable"),
    # Смена и восстановление пароля
    path(
        "profile/password/",
        auth_views.PasswordChangeView.as_view(success_url=reverse_lazy("password_change_done")),
        name="password_change",
    ),
    path(
        "profile/password/done/",
        auth_views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    path("password-reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path(
        "password-reset/sent/",
        auth_views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("robots.txt", views.robots_txt),
    path("healthz/", views.healthz),
]
