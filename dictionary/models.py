import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


def unique_slug(instance, value, max_length=80):
    """Латинский slug; для кириллицы — транслит, чтобы адреса были читаемыми."""
    base = slugify(translit(value))[: max_length - 6] or "item"
    slug, n = base, 2
    model = type(instance)
    while model.objects.filter(slug=slug).exclude(pk=instance.pk).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


_TRANSLIT = dict(
    zip(
        "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
        "a b v g d e e zh z i y k l m n o p r s t u f h ts ch sh sch  y  e yu ya".split(" "),
    )
)


def translit(text):
    return "".join(_TRANSLIT.get(ch, ch) for ch in text.lower())


class Tag(models.Model):
    """IT-тема: «Веб», «Базы данных», «Безопасность»…"""

    name = models.CharField("название", max_length=60, unique=True)
    slug = models.SlugField("адрес", max_length=80, unique=True, blank=True)
    description = models.CharField("описание", max_length=200, blank=True)

    class Meta:
        verbose_name = "тег (тема)"
        verbose_name_plural = "теги (темы)"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)


class Entry(models.Model):
    """Словарная запись — одно английское слово или выражение."""

    word = models.CharField("слово (англ.)", max_length=120, db_index=True)
    translation = models.CharField("перевод", max_length=255)
    transcription = models.CharField("транскрипция", max_length=120, blank=True)
    description = models.TextField("описание (англ.)", blank=True)
    example = models.CharField("пример", max_length=300, blank=True)
    tags = models.ManyToManyField(Tag, verbose_name="темы", related_name="entries", blank=True)
    created_at = models.DateTimeField("добавлено", auto_now_add=True)
    updated_at = models.DateTimeField("изменено", auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="кто добавил",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        editable=False,
    )

    class Meta:
        verbose_name = "словарная запись"
        verbose_name_plural = "словарные записи"
        ordering = ["word"]
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower("word"), name="unique_entry_word_ci"
            )
        ]

    def __str__(self):
        return f"{self.word} — {self.translation}"

    def get_absolute_url(self):
        return reverse("entry_detail", args=[self.pk])

    def as_card(self):
        return {
            "id": self.pk,
            "word": self.word,
            "translation": self.translation,
            "transcription": self.transcription,
            "description": self.description,
            "example": self.example,
        }


class CardSet(models.Model):
    """Набор карточек, который составляют сотрудники в панели наполнения."""

    title = models.CharField("название", max_length=120)
    slug = models.SlugField("адрес", max_length=80, unique=True, blank=True)
    description = models.CharField("описание", max_length=300, blank=True)
    entries = models.ManyToManyField(Entry, verbose_name="слова", related_name="card_sets")
    is_published = models.BooleanField("опубликован", default=True)
    created_at = models.DateTimeField("создан", auto_now_add=True)

    class Meta:
        verbose_name = "набор карточек"
        verbose_name_plural = "наборы карточек"
        ordering = ["title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("set_detail", args=[self.slug])


class Topic(models.Model):
    """Персональный словарь ученика: своя тема со словами."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="topics"
    )
    title = models.CharField("название", max_length=80)
    description = models.CharField("описание", max_length=200, blank=True)
    entries = models.ManyToManyField(
        Entry, verbose_name="слова из словаря", related_name="topics", blank=True
    )
    created_at = models.DateTimeField("создан", auto_now_add=True)

    class Meta:
        verbose_name = "персональный словарь"
        verbose_name_plural = "персональные словари"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("topic_detail", args=[self.pk])

    def cards(self):
        cards = [e.as_card() for e in self.entries.all()]
        cards += [w.as_card() for w in self.own_words.all()]
        return cards

    def word_count(self):
        return self.entries.count() + self.own_words.count()


class TopicWord(models.Model):
    """Своё слово ученика внутри персонального словаря."""

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="own_words")
    word = models.CharField("слово (англ.)", max_length=120)
    translation = models.CharField("перевод", max_length=255)
    transcription = models.CharField("транскрипция", max_length=120, blank=True)
    note = models.CharField("заметка", max_length=300, blank=True)

    class Meta:
        verbose_name = "своё слово"
        verbose_name_plural = "свои слова"
        ordering = ["word"]

    def __str__(self):
        return self.word

    def as_card(self):
        return {
            "id": f"own-{self.pk}",
            "word": self.word,
            "translation": self.translation,
            "transcription": self.transcription,
            "description": self.note,
            "example": "",
        }


class Article(models.Model):
    LEVELS = [(lvl, lvl) for lvl in ("A1", "A2", "B1", "B2", "C1", "C2")]

    title = models.CharField("заголовок", max_length=160)
    slug = models.SlugField("адрес", max_length=80, unique=True, blank=True)
    level = models.CharField("уровень", max_length=2, choices=LEVELS, default="B1")
    summary = models.CharField("кратко (по-русски)", max_length=300, blank=True)
    body = models.TextField(
        "текст (англ.)", help_text="Обычный текст. Пустая строка — новый абзац."
    )
    tags = models.ManyToManyField(Tag, verbose_name="темы", related_name="articles", blank=True)
    reading_minutes = models.PositiveSmallIntegerField("минут на чтение", default=5)
    is_published = models.BooleanField("опубликована", default=True)
    created_at = models.DateTimeField("создана", auto_now_add=True)

    class Meta:
        verbose_name = "статья"
        verbose_name_plural = "статьи"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.title)
        if self.body:
            self.reading_minutes = max(1, round(len(self.body.split()) / 180))
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("article_detail", args=[self.slug])


def avatar_path(instance, filename):
    """Случайное имя файла: исходное имя от пользователя на диск не попадает."""
    ext = filename.rsplit(".", 1)[-1].lower()
    return f"avatars/{uuid.uuid4().hex}.{ext}"


handle_validator = RegexValidator(
    r"^[A-Za-z0-9_.-]{0,64}$", "Только латинские буквы, цифры, точка, дефис и подчёркивание."
)


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    avatar = models.ImageField("аватар", upload_to=avatar_path, blank=True)
    group = models.CharField("группа", max_length=40, blank=True)
    bio = models.CharField("о себе", max_length=300, blank=True)
    telegram = models.CharField(
        "Telegram", max_length=64, blank=True, validators=[handle_validator],
        help_text="Имя пользователя без @",
    )
    vk = models.CharField("ВКонтакте", max_length=64, blank=True, validators=[handle_validator])
    github = models.CharField("GitHub", max_length=64, blank=True, validators=[handle_validator])

    favorite_entries = models.ManyToManyField(Entry, blank=True, related_name="+")
    favorite_sets = models.ManyToManyField(CardSet, blank=True, related_name="+")
    favorite_tags = models.ManyToManyField(Tag, blank=True, related_name="+")

    current_login = models.DateTimeField(null=True, blank=True, editable=False)
    previous_login = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "профиль"
        verbose_name_plural = "профили"

    def __str__(self):
        return f"Профиль {self.user}"


class TrainingResult(models.Model):
    MODES = [("cards", "Карточки"), ("quiz", "Квиз"), ("write", "Письмо")]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="results"
    )
    mode = models.CharField(max_length=10, choices=MODES)
    source = models.CharField(max_length=120, blank=True)
    correct = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "результат тренировки"
        verbose_name_plural = "результаты тренировок"
        ordering = ["-created_at"]


class SignupLog(models.Model):
    """Журнал регистраций — для лимита «не больше N аккаунтов с IP в час»."""

    ip = models.GenericIPAddressField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "регистрация (журнал)"
        verbose_name_plural = "регистрации (журнал)"
