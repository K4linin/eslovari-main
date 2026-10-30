import json
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice
from openpyxl import Workbook

from .admin import import_entries_from_excel
from .forms import FORM_STAMP_SALT
from .models import Entry, SignupLog, Tag, Topic, TrainingResult

User = get_user_model()
PASSWORD = "Str0ngPassw0rd!"


def old_stamp(seconds_ago=60):
    import time
    return signing.dumps(time.time() - seconds_ago, salt=FORM_STAMP_SALT)


def totp_now(device):
    return f"{totp(device.bin_key, device.step, device.t0, device.digits, device.drift):06d}"


class PublicPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_data", verbosity=0)

    def test_pages_open(self):
        tag = Tag.objects.first()
        entry = Entry.objects.first()
        for url in [
            "/", f"/?q=deploy", f"/?tag={tag.slug}", "/sets/", "/articles/", "/articles/?level=B1",
            "/trainer/", "/trainer/?mode=quiz", f"/trainer/?mode=write&tag={tag.slug}",
            entry.get_absolute_url(), "/login/", "/register/", "/password-reset/", "/robots.txt",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_search_finds_word(self):
        response = self.client.get("/?q=deploy")
        self.assertContains(response, "развёртывать")

    def test_security_headers(self):
        response = self.client.get("/")
        self.assertIn("script-src 'self'", response["Content-Security-Policy"])
        self.assertEqual(response["X-Frame-Options"], "DENY")

    def test_private_pages_require_login(self):
        for url in ["/profile/", "/my/", "/favorites/"]:
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f"/login/?next={url}")

    def test_search_output_is_escaped(self):
        response = self.client.get("/?q=<script>alert(1)</script>")
        self.assertNotContains(response, "<script>alert(1)</script>")


class RegistrationTests(TestCase):
    def data(self, **extra):
        data = {
            "username": "student1", "email": "s1@example.com",
            "password1": PASSWORD, "password2": PASSWORD,
            "website": "", "stamp": old_stamp(),
        }
        data.update(extra)
        return data

    def test_register_ok(self):
        response = self.client.post("/register/", self.data())
        self.assertRedirects(response, "/")
        user = User.objects.get(username="student1")
        self.assertTrue(user.password.startswith("argon2"))
        self.assertTrue(hasattr(user, "profile"))

    def test_honeypot_blocks_bots(self):
        self.client.post("/register/", self.data(website="http://spam"))
        self.assertFalse(User.objects.filter(username="student1").exists())

    def test_too_fast_submission_blocked(self):
        self.client.post("/register/", self.data(stamp=old_stamp(0)))
        self.assertFalse(User.objects.exists())

    def test_reserved_username(self):
        response = self.client.post("/register/", self.data(username="Admin"))
        self.assertContains(response, "зарезервировано")

    def test_weak_password(self):
        response = self.client.post("/register/", self.data(password1="onlyletters", password2="onlyletters"))
        self.assertContains(response, "и буквы, и цифры")
        response = self.client.post("/register/", self.data(password1="Ab1short", password2="Ab1short"))
        self.assertContains(response, "10")

    @override_settings(SIGNUP_LIMIT_PER_HOUR=2)
    def test_ip_limit(self):
        SignupLog.objects.create(ip="127.0.0.1")
        SignupLog.objects.create(ip="127.0.0.1")
        response = self.client.post("/register/", self.data())
        self.assertEqual(response.status_code, 429)
        self.assertFalse(User.objects.exists())


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ivan", "ivan@example.com", PASSWORD)

    def test_login_with_email_and_previous_login(self):
        self.client.post("/login/", {"username": "ivan@example.com", "password": PASSWORD})
        self.client.post("/logout/")
        response = self.client.post("/login/", {"username": "ivan", "password": PASSWORD})
        self.assertRedirects(response, "/")
        self.user.profile.refresh_from_db()
        self.assertIsNotNone(self.user.profile.previous_login)

    def test_remember_me(self):
        self.client.post("/login/", {"username": "ivan", "password": PASSWORD})
        self.assertTrue(self.client.session.get_expire_at_browser_close())
        self.client.post("/logout/")
        self.client.post("/login/", {"username": "ivan", "password": PASSWORD, "remember_me": "on"})
        self.assertFalse(self.client.session.get_expire_at_browser_close())

    def test_bruteforce_lockout(self):
        for _ in range(5):
            self.client.post("/login/", {"username": "ivan", "password": "wrong-password-1"})
        response = self.client.post("/login/", {"username": "ivan", "password": PASSWORD})
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_open_redirect_blocked(self):
        response = self.client.post(
            "/login/?next=https://evil.example/", {"username": "ivan", "password": PASSWORD}
        )
        self.assertRedirects(response, "/", fetch_redirect_response=False)


class TwoFactorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("olga", "olga@example.com", PASSWORD)
        self.client.force_login(self.user)

    def enable_2fa(self):
        self.client.get("/profile/2fa/")
        device = TOTPDevice.objects.get(user=self.user)
        response = self.client.post("/profile/2fa/", {"token": totp_now(device)})
        self.assertRedirects(response, "/profile/2fa/codes/", fetch_redirect_response=False)
        codes = self.client.session["backup_codes"]
        self.assertEqual(len(codes), 8)
        self.client.post("/logout/")
        return device, codes

    def test_setup_and_login_with_totp(self):
        device, _ = self.enable_2fa()
        response = self.client.post("/login/", {"username": "olga", "password": PASSWORD})
        self.assertRedirects(response, "/login/2fa/")
        self.assertNotIn("_auth_user_id", self.client.session)
        response = self.client.post("/login/2fa/", {"token": "000000"})
        self.assertContains(response, "Неверный код")
        # Тот же код дважды не принимается (защита от повтора) — сбрасываем для теста
        TOTPDevice.objects.filter(pk=device.pk).update(last_t=-1)
        device.refresh_from_db()
        with mock.patch.object(TOTPDevice, "verify_is_allowed", return_value=(True, None)):
            response = self.client.post("/login/2fa/", {"token": totp_now(device)})
        self.assertRedirects(response, "/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_backup_code_works_once(self):
        _, codes = self.enable_2fa()
        self.client.post("/login/", {"username": "olga", "password": PASSWORD})
        response = self.client.post("/login/2fa/", {"token": codes[0].upper()})
        self.assertRedirects(response, "/")
        self.assertEqual(StaticToken.objects.count(), 7)
        self.client.post("/logout/")
        self.client.post("/login/", {"username": "olga", "password": PASSWORD})
        response = self.client.post("/login/2fa/", {"token": codes[0]})
        self.assertEqual(response.status_code, 200)

    def test_disable_requires_password(self):
        self.enable_2fa()
        self.client.force_login(self.user)
        self.client.post("/profile/2fa/disable/", {"password": "nope"})
        self.assertTrue(TOTPDevice.objects.filter(user=self.user).exists())
        self.client.post("/profile/2fa/disable/", {"password": PASSWORD})
        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())
        self.assertFalse(StaticDevice.objects.filter(user=self.user).exists())


class AdminAccessTests(TestCase):
    def test_admin_login_goes_through_site_login(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        response = self.client.get(response["Location"])
        self.assertRedirects(response, "/login/?next=/admin/")

    def test_non_staff_forbidden(self):
        user = User.objects.create_user("pupil", "p@example.com", PASSWORD)
        self.client.force_login(user)
        response = self.client.get("/admin/", follow=True)
        self.assertEqual(response.status_code, 403)

    @override_settings(ADMIN_REQUIRE_2FA=True)
    def test_staff_needs_2fa_when_required(self):
        staff = User.objects.create_user("editor", "e@example.com", PASSWORD, is_staff=True)
        self.client.force_login(staff)
        response = self.client.get("/admin/", follow=True)
        self.assertEqual(response.request["PATH_INFO"], "/profile/")


class ExcelImportTests(TestCase):
    def make_xlsx(self, rows):
        wb = Workbook()
        ws = wb.active
        ws.append(["word", "translation", "transcription", "description"])
        for row in rows:
            ws.append(row)
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    def test_import(self):
        Entry.objects.create(word="Cache", translation="кэш (старый)")
        tag = Tag.objects.create(name="Веб")
        file = self.make_xlsx([
            ["cache", "кэш", "[kæʃ]", "Fast temporary storage."],
            ["proxy", "прокси", None, None],
            [None, "без слова", None, None],
            ["no-translation", None, None, None],
        ])
        stats = import_entries_from_excel(file, tags=[tag])
        self.assertEqual(stats, {"created": 1, "updated": 1, "skipped": 2})
        self.assertEqual(Entry.objects.get(word="Cache").translation, "кэш")
        self.assertEqual(tag.entries.count(), 2)

    def test_admin_import_view_and_export(self):
        admin = User.objects.create_superuser("boss", "b@example.com", PASSWORD)
        self.client.force_login(admin)
        upload = SimpleUploadedFile(
            "words.xlsx", self.make_xlsx([["kernel", "ядро", "", ""]]).read()
        )
        response = self.client.post(
            reverse("admin:dictionary_entry_import"), {"file": upload, "update_existing": "on"}
        )
        self.assertRedirects(response, reverse("admin:dictionary_entry_changelist"))
        self.assertTrue(Entry.objects.filter(word="kernel").exists())

        response = self.client.post(
            reverse("admin:dictionary_entry_changelist"),
            {"action": "export_to_excel", "_selected_action": [Entry.objects.get(word="kernel").pk]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response["Content-Type"])

    def test_rejects_non_xlsx(self):
        admin = User.objects.create_superuser("boss", "b@example.com", PASSWORD)
        self.client.force_login(admin)
        upload = SimpleUploadedFile("evil.xlsx", b"not a zip")
        response = self.client.post(reverse("admin:dictionary_entry_import"), {"file": upload})
        self.assertContains(response, "Не получилось прочитать файл")


class StudentFeatureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_data", verbosity=0)
        cls.user = User.objects.create_user("masha", "m@example.com", PASSWORD)
        cls.other = User.objects.create_user("petya", "pe@example.com", PASSWORD)

    def setUp(self):
        self.client.force_login(self.user)

    def test_favorites_toggle(self):
        entry = Entry.objects.first()
        url = f"/fav/entry/{entry.pk}/"
        response = self.client.post(url, HTTP_ACCEPT="application/json")
        self.assertEqual(response.json(), {"active": True})
        self.assertContains(self.client.get("/favorites/"), entry.word)
        self.assertEqual(self.client.post(url, HTTP_ACCEPT="application/json").json(), {"active": False})
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_topics_are_private(self):
        self.client.post("/my/", {"title": "Мои слова"})
        topic = Topic.objects.get(owner=self.user)
        self.client.post(f"/my/{topic.pk}/", {"action": "add_word", "w-word": "sprint", "w-translation": "спринт"})
        self.client.post(f"/word/{Entry.objects.first().pk}/to-topic/", {"topic": topic.pk})
        self.assertEqual(topic.word_count(), 2)
        response = self.client.get(f"/trainer/?mode=quiz&topic={topic.pk}")
        self.assertContains(response, "sprint")

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f"/my/{topic.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/trainer/?topic={topic.pk}").status_code, 404)

    def test_trainer_result_saved_and_validated(self):
        ok = self.client.post(
            "/trainer/result/", json.dumps({"mode": "quiz", "total": 10, "correct": 7}),
            content_type="application/json",
        )
        self.assertEqual(ok.status_code, 200)
        bad = self.client.post(
            "/trainer/result/", json.dumps({"mode": "quiz", "total": 1, "correct": 7}),
            content_type="application/json",
        )
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(TrainingResult.objects.count(), 1)
        self.assertContains(self.client.get("/profile/"), "70%")
