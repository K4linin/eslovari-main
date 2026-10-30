from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core import signing
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Profile, Tag, Topic, TopicWord
from .validators import validate_username_not_reserved

User = get_user_model()

FORM_STAMP_SALT = "eslovari.signup.stamp"


class LoginForm(AuthenticationForm):
    remember_me = forms.BooleanField(label="Запомнить меня на 30 дней", required=False)

    error_messages = {
        "invalid_login": "Неверное имя пользователя или пароль.",
        "inactive": "Этот аккаунт отключён.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Имя пользователя или email"
        self.fields["username"].widget.attrs.update(autocomplete="username", autofocus=True)
        self.fields["password"].widget.attrs.update(autocomplete="current-password")

    def clean_username(self):
        # Разрешаем входить по email: подставляем соответствующий логин
        value = self.cleaned_data["username"].strip()
        if "@" in value:
            user = User.objects.filter(email__iexact=value).first()
            if user:
                return user.get_username()
        return value


class SignupForm(UserCreationForm):
    email = forms.EmailField(label="Email", help_text="Нужен для восстановления пароля.")
    # Ловушка для ботов: поле скрыто от людей через CSS, боты его заполняют
    website = forms.CharField(required=False, label="Не заполняйте это поле")
    stamp = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = "Латиница, цифры и символы @/./+/-/_ — до 150 знаков."
        self.fields["username"].validators.append(validate_username_not_reserved)
        self.fields["website"].widget.attrs.update(autocomplete="off", tabindex="-1")
        self.fields["password1"].widget.attrs.update(
            autocomplete="new-password", **{"data-strength": "1"}
        )
        if not self.is_bound:
            self.initial["stamp"] = signing.dumps(timezone.now().timestamp(), salt=FORM_STAMP_SALT)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Аккаунт с таким email уже существует.")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("website"):
            raise ValidationError("Похоже, форму заполнил бот.", code="bot")
        try:
            started = signing.loads(
                self.data.get("stamp", ""), salt=FORM_STAMP_SALT, max_age=60 * 60 * 24
            )
        except signing.BadSignature:
            raise ValidationError(
                "Форма устарела. Обновите страницу и попробуйте ещё раз.", code="stamp"
            )
        if timezone.now().timestamp() - float(started) < settings.SIGNUP_MIN_SECONDS:
            raise ValidationError("Слишком быстро! Проверьте данные и отправьте ещё раз.", code="fast")
        return cleaned


class OTPTokenForm(forms.Form):
    token = forms.CharField(
        label="Код из приложения или резервный код",
        max_length=16,
        widget=forms.TextInput(
            attrs={"autocomplete": "one-time-code", "inputmode": "text", "autofocus": True}
        ),
    )

    def clean_token(self):
        return self.cleaned_data["token"].replace(" ", "").strip()


class TOTPConfirmForm(forms.Form):
    token = forms.RegexField(
        label="6-значный код из приложения",
        regex=r"^\d{6}$",
        error_messages={"invalid": "Введите 6 цифр."},
        widget=forms.TextInput(
            attrs={"autocomplete": "one-time-code", "inputmode": "numeric", "autofocus": True}
        ),
    )


class PasswordConfirmForm(forms.Form):
    password = forms.CharField(
        label="Текущий пароль",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise ValidationError("Неверный пароль.")
        return password


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Этот email уже используется другим аккаунтом.")
        return email


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("avatar", "group", "bio", "telegram", "vk", "github")
        widgets = {"avatar": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"})}

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar and hasattr(avatar, "size"):
            if avatar.size > settings.AVATAR_MAX_BYTES:
                raise ValidationError("Файл больше 2 МБ.")
            ext = avatar.name.rsplit(".", 1)[-1].lower()
            if ext not in {"jpg", "jpeg", "png", "webp"}:
                raise ValidationError("Подойдут только JPG, PNG или WEBP.")
        return avatar

    def clean_telegram(self):
        return self.cleaned_data["telegram"].lstrip("@")


class TopicForm(forms.ModelForm):
    class Meta:
        model = Topic
        fields = ("title", "description")


class TopicWordForm(forms.ModelForm):
    class Meta:
        model = TopicWord
        fields = ("word", "translation", "transcription", "note")


class ExcelImportForm(forms.Form):
    file = forms.FileField(
        label="Файл Excel (.xlsx)",
        widget=forms.ClearableFileInput(
            attrs={"accept": ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        ),
    )
    tags = forms.ModelMultipleChoiceField(
        Tag.objects.all(),
        required=False,
        label="Добавить всем словам темы",
        widget=forms.CheckboxSelectMultiple,
    )
    update_existing = forms.BooleanField(
        label="Обновлять перевод и описание, если слово уже есть",
        required=False,
        initial=True,
    )

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith(".xlsx"):
            raise ValidationError("Нужен файл в формате .xlsx (Excel 2007 и новее).")
        if f.size > settings.EXCEL_MAX_BYTES:
            raise ValidationError("Файл больше 5 МБ — разбейте его на части.")
        return f
