import json
import random
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_safe, require_POST
from django_otp import user_has_device

from .forms import ProfileForm, TopicForm, TopicWordForm, UserForm
from .models import Article, CardSet, Entry, Profile, Tag, Topic, TopicWord, TrainingResult

TRAINER_MODES = {
    "cards": {"title": "Карточки", "hint": "Листай и переворачивай"},
    "quiz": {"title": "Квиз", "hint": "Выбери перевод из четырёх"},
    "write": {"title": "Письмо", "hint": "Напечатай слово сам"},
}
TRAINER_SESSION_SIZE = 20


def _profile(request):
    if not request.user.is_authenticated:
        return None
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return profile


def _favorite_ids(profile):
    if profile is None:
        return set(), set(), set()
    return (
        set(profile.favorite_entries.values_list("pk", flat=True)),
        set(profile.favorite_sets.values_list("pk", flat=True)),
        set(profile.favorite_tags.values_list("pk", flat=True)),
    )


def _safe_next(request, fallback="home"):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return fallback


def _search_entries(request, queryset):
    q = request.GET.get("q", "").strip()[:100]
    tag_slug = request.GET.get("tag", "").strip()
    current_tag = None
    if q:
        queryset = queryset.filter(
            Q(word__icontains=q)
            | Q(translation__icontains=q)
            | Q(description__icontains=q)
            | Q(tags__name__icontains=q)
        )
    if tag_slug:
        current_tag = Tag.objects.filter(slug=tag_slug).first()
        if current_tag:
            queryset = queryset.filter(tags=current_tag)
    return queryset.prefetch_related("tags").distinct(), q, current_tag


# --- Главная: словарь, режимы, наборы, статьи ------------------------------------


def _word_of_day():
    count = Entry.objects.count()
    if not count:
        return None
    return Entry.objects.order_by("pk")[date.today().toordinal() % count]


@require_safe
def home(request):
    entries, q, current_tag = _search_entries(request, Entry.objects.all())
    page = Paginator(entries, 24).get_page(request.GET.get("page"))
    profile = _profile(request)
    fav_entries, fav_sets, fav_tags = _favorite_ids(profile)

    context = {
        "page": page,
        "q": q,
        "current_tag": current_tag,
        "tags": Tag.objects.annotate(n=Count("entries")).filter(n__gt=0),
        "sets": CardSet.objects.filter(is_published=True)
        .annotate(n=Count("entries"))
        .order_by("-created_at")[:6],
        "articles": Article.objects.filter(is_published=True)[:3],
        "modes": TRAINER_MODES,
        "stats": {
            "words": Entry.objects.count(),
            "tags": Tag.objects.count(),
            "articles": Article.objects.filter(is_published=True).count(),
        },
        "fav_entries": fav_entries,
        "fav_sets": fav_sets,
        "fav_tags": fav_tags,
        "word_of_day": _word_of_day(),
    }
    return render(request, "dictionary/home.html", context)


@require_safe
def entry_detail(request, pk):
    entry = get_object_or_404(Entry.objects.prefetch_related("tags"), pk=pk)
    related = (
        Entry.objects.filter(tags__in=entry.tags.all()).exclude(pk=entry.pk).distinct()[:6]
    )
    profile = _profile(request)
    fav_entries, _, _ = _favorite_ids(profile)
    topics = request.user.topics.all() if request.user.is_authenticated else []
    return render(
        request,
        "dictionary/entry_detail.html",
        {"entry": entry, "related": related, "fav_entries": fav_entries, "topics": topics},
    )


# --- Наборы карточек ---------------------------------------------------------------


@require_safe
def set_list(request):
    profile = _profile(request)
    _, fav_sets, _ = _favorite_ids(profile)
    sets = CardSet.objects.filter(is_published=True).annotate(n=Count("entries"))
    return render(request, "dictionary/set_list.html", {"sets": sets, "fav_sets": fav_sets})


@require_safe
def set_detail(request, slug):
    card_set = get_object_or_404(CardSet, slug=slug, is_published=True)
    profile = _profile(request)
    fav_entries, fav_sets, _ = _favorite_ids(profile)
    return render(
        request,
        "dictionary/set_detail.html",
        {
            "set": card_set,
            "entries": card_set.entries.prefetch_related("tags"),
            "fav_entries": fav_entries,
            "fav_sets": fav_sets,
            "modes": TRAINER_MODES,
        },
    )


# --- Тренажёр ----------------------------------------------------------------------


def _trainer_source(request):
    """Возвращает (название, список карточек, query-строка источника)."""
    params = request.GET
    if params.get("set"):
        card_set = get_object_or_404(CardSet, slug=params["set"], is_published=True)
        return f"Набор «{card_set.title}»", [e.as_card() for e in card_set.entries.all()], f"set={card_set.slug}"
    if params.get("topic"):
        if not request.user.is_authenticated:
            raise Http404
        topic = get_object_or_404(Topic, pk=params["topic"], owner=request.user)
        return f"Мой словарь «{topic.title}»", topic.cards(), f"topic={topic.pk}"
    if params.get("favorites"):
        profile = _profile(request)
        if profile is None:
            raise Http404
        return "Избранные слова", [e.as_card() for e in profile.favorite_entries.all()], "favorites=1"
    if params.get("tag"):
        tag = get_object_or_404(Tag, slug=params["tag"])
        return f"Тема «{tag.name}»", [e.as_card() for e in tag.entries.all()], f"tag={tag.slug}"
    ids = list(Entry.objects.values_list("pk", flat=True))
    sample = random.sample(ids, min(len(ids), TRAINER_SESSION_SIZE))
    return "Весь словарь", [e.as_card() for e in Entry.objects.filter(pk__in=sample)], ""


@require_safe
def trainer(request):
    mode = request.GET.get("mode", "cards")
    if mode not in TRAINER_MODES:
        mode = "cards"
    title, cards, source_qs = _trainer_source(request)
    random.shuffle(cards)
    cards = cards[:TRAINER_SESSION_SIZE]

    # Варианты-«обманки» для квиза: переводы других слов словаря
    own = {c["translation"] for c in cards}
    pool = list(
        Entry.objects.exclude(translation__in=own)
        .order_by("?")
        .values_list("translation", flat=True)[:80]
    )
    data = {"mode": mode, "cards": cards, "distractors": pool, "source": title}
    return render(
        request,
        "dictionary/trainer.html",
        {
            "mode": mode,
            "mode_info": TRAINER_MODES[mode],
            "modes": TRAINER_MODES,
            "title": title,
            "source_qs": source_qs,
            "trainer_data": data,
            "count": len(cards),
        },
    )


@login_required
@require_POST
def trainer_result(request):
    try:
        data = json.loads(request.body.decode())
        mode = str(data["mode"])
        total = int(data["total"])
        correct = int(data["correct"])
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return JsonResponse({"ok": False}, status=400)
    if mode not in TRAINER_MODES or not (0 <= correct <= total <= 500):
        return JsonResponse({"ok": False}, status=400)
    TrainingResult.objects.create(
        user=request.user,
        mode=mode,
        source=str(data.get("source", ""))[:120],
        correct=correct,
        total=total,
    )
    return JsonResponse({"ok": True})


# --- Персональные словари ------------------------------------------------------------


@login_required
def topic_list(request):
    form = TopicForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if request.user.topics.count() >= 100:
            messages.error(request, "Можно создать не больше 100 словарей.")
        else:
            topic = form.save(commit=False)
            topic.owner = request.user
            topic.save()
            messages.success(request, f"Словарь «{topic.title}» создан.")
            return redirect(topic)
    topics = request.user.topics.annotate(n_entries=Count("entries", distinct=True), n_own=Count("own_words", distinct=True))
    return render(request, "dictionary/topic_list.html", {"topics": topics, "form": form})


@login_required
def topic_detail(request, pk):
    topic = get_object_or_404(Topic, pk=pk, owner=request.user)
    word_form = TopicWordForm(prefix="w")
    edit_form = TopicForm(instance=topic, prefix="t")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_word":
            word_form = TopicWordForm(request.POST, prefix="w")
            if word_form.is_valid():
                if topic.own_words.count() >= 500:
                    messages.error(request, "В одном словаре — не больше 500 своих слов.")
                else:
                    word = word_form.save(commit=False)
                    word.topic = topic
                    word.save()
                    messages.success(request, f"Слово «{word.word}» добавлено.")
                    return redirect(topic)
        elif action == "edit":
            edit_form = TopicForm(request.POST, instance=topic, prefix="t")
            if edit_form.is_valid():
                edit_form.save()
                messages.success(request, "Изменения сохранены.")
                return redirect(topic)
        elif action == "remove_entry":
            topic.entries.remove(*Entry.objects.filter(pk=request.POST.get("entry")))
            return redirect(topic)
        elif action == "remove_word":
            TopicWord.objects.filter(topic=topic, pk=request.POST.get("word")).delete()
            return redirect(topic)
        elif action == "delete":
            title = topic.title
            topic.delete()
            messages.success(request, f"Словарь «{title}» удалён.")
            return redirect("topic_list")

    return render(
        request,
        "dictionary/topic_detail.html",
        {
            "topic": topic,
            "entries": topic.entries.all(),
            "own_words": topic.own_words.all(),
            "word_form": word_form,
            "edit_form": edit_form,
            "modes": TRAINER_MODES,
        },
    )


@login_required
@require_POST
def topic_add_entry(request, pk):
    entry = get_object_or_404(Entry, pk=pk)
    topic = get_object_or_404(Topic, pk=request.POST.get("topic"), owner=request.user)
    topic.entries.add(entry)
    messages.success(request, f"«{entry.word}» добавлено в «{topic.title}».")
    return redirect(_safe_next(request, entry.get_absolute_url()))


# --- Статьи --------------------------------------------------------------------------


@require_safe
def article_list(request):
    level = request.GET.get("level", "")
    articles = Article.objects.filter(is_published=True).prefetch_related("tags")
    if level in dict(Article.LEVELS):
        articles = articles.filter(level=level)
    else:
        level = ""
    page = Paginator(articles, 9).get_page(request.GET.get("page"))
    return render(
        request,
        "dictionary/article_list.html",
        {"page": page, "level": level, "levels": [lvl for lvl, _ in Article.LEVELS]},
    )


@require_safe
def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug, is_published=True)
    more = Article.objects.filter(is_published=True).exclude(pk=article.pk)[:3]
    return render(request, "dictionary/article_detail.html", {"article": article, "more": more})


# --- Избранное -----------------------------------------------------------------------

FAVORITE_KINDS = {
    "entry": (Entry, "favorite_entries"),
    "set": (CardSet, "favorite_sets"),
    "tag": (Tag, "favorite_tags"),
}


@login_required
@require_POST
def toggle_favorite(request, kind, pk):
    if kind not in FAVORITE_KINDS:
        raise Http404
    model, field = FAVORITE_KINDS[kind]
    obj = get_object_or_404(model, pk=pk)
    relation = getattr(_profile(request), field)
    if relation.filter(pk=obj.pk).exists():
        relation.remove(obj)
        active = False
    else:
        relation.add(obj)
        active = True
    if request.headers.get("Accept") == "application/json":
        return JsonResponse({"active": active})
    return redirect(_safe_next(request))


@login_required
@require_safe
def favorites(request):
    profile = _profile(request)
    return render(
        request,
        "dictionary/favorites.html",
        {
            "entries": profile.favorite_entries.prefetch_related("tags"),
            "sets": profile.favorite_sets.annotate(n=Count("entries")),
            "tags": profile.favorite_tags.annotate(n=Count("entries")),
            "fav_entries": set(profile.favorite_entries.values_list("pk", flat=True)),
            "fav_sets": set(profile.favorite_sets.values_list("pk", flat=True)),
            "fav_tags": set(profile.favorite_tags.values_list("pk", flat=True)),
        },
    )


# --- Профиль -------------------------------------------------------------------------


@login_required
def profile(request):
    prof = _profile(request)
    user_form = UserForm(request.POST or None, instance=request.user, prefix="u")
    profile_form = ProfileForm(request.POST or None, request.FILES or None, instance=prof, prefix="p")
    if request.method == "POST" and user_form.is_valid() and profile_form.is_valid():
        old_avatar = Profile.objects.get(pk=prof.pk).avatar
        user_form.save()
        saved = profile_form.save()
        if old_avatar and old_avatar.name != saved.avatar.name:
            old_avatar.delete(save=False)
        messages.success(request, "Профиль сохранён.")
        return redirect("profile")

    results = request.user.results.all()
    totals = {"sessions": results.count(), "correct": 0, "total": 0}
    for r in results:
        totals["correct"] += r.correct
        totals["total"] += r.total
    totals["accuracy"] = round(100 * totals["correct"] / totals["total"]) if totals["total"] else 0

    return render(
        request,
        "dictionary/profile.html",
        {
            "user_form": user_form,
            "profile_form": profile_form,
            "prof": prof,
            "has_2fa": user_has_device(request.user),
            "backup_left": sum(
                d.token_set.count()
                for d in request.user.staticdevice_set.filter(confirmed=True)
            ),
            "results": results[:8],
            "totals": totals,
            "topics_count": request.user.topics.count(),
        },
    )


# --- Служебное -----------------------------------------------------------------------


@require_safe
def robots_txt(request):
    # Адрес админки сюда не пишем — иначе robots.txt подскажет его сканерам
    lines = [
        "User-agent: *",
        "Disallow: /login/",
        "Disallow: /register/",
        "Disallow: /profile/",
        "Disallow: /my/",
        "Disallow: /favorites/",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


@require_safe
def healthz(request):
    return HttpResponse("ok", content_type="text/plain")


def page_not_found(request, exception=None):
    return render(request, "dictionary/error.html", {"code": 404, "text": "Такой страницы нет"}, status=404)


def server_error(request):
    return render(request, "dictionary/error.html", {"code": 500, "text": "Что-то сломалось. Мы уже чиним"}, status=500)
