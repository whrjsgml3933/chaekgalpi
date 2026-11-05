import tempfile
from io import BytesIO

from PIL import Image
from django.contrib.auth import SESSION_KEY, get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

User = get_user_model()


class AccountFlowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="reader", password="InitialPass739!")
        self.other = User.objects.create_user(username="other", password="OtherPass739!")

    def signup_data(self, **extra):
        data = dict(
            username="newreader",
            password1="FreshPass739!",
            password2="FreshPass739!",
            email="new@example.com",
            first_name="Reader",
            last_name="Kim",
            gender="female",
            age=25,
            birth_date="2001-01-01",
            weekly_reading_time=3,
            yearly_reading_count=12,
        )
        data.update(extra)
        return data

    def test_public_pages_and_root(self):
        self.assertRedirects(self.client.get("/"), reverse("books:index"))
        for url in [
            reverse("accounts:login"),
            reverse("accounts:signup"),
            reverse("accounts:profile", args=[self.owner.pk]),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_signup_creates_user_and_session(self):
        response = self.client.post(reverse("accounts:signup"), self.signup_data())
        self.assertRedirects(response, reverse("books:index"))
        user = User.objects.get(username="newreader")
        self.assertEqual(user.gender, "female")
        self.assertEqual(user.yearly_reading_count, 12)
        self.assertEqual(int(self.client.session[SESSION_KEY]), user.pk)

    def test_invalid_signup_does_not_save(self):
        for data in [
            self.signup_data(password2="mismatch"),
            self.signup_data(username="reader"),
            self.signup_data(gender="invalid"),
        ]:
            with self.subTest(data=data):
                response = self.client.post(reverse("accounts:signup"), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertEqual(User.objects.count(), 2)

    def test_login_logout_and_invalid_login(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "reader", "password": "wrong"}
        )
        self.assertTrue(response.context["form"].errors)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertRedirects(
            self.client.post(
                reverse("accounts:login"), {"username": "reader", "password": "InitialPass739!"}
            ),
            reverse("books:index"),
        )
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("accounts:logout")), reverse("books:index"))
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_authenticated_signup_and_login_redirect(self):
        self.client.force_login(self.owner)
        for name in ["login", "signup"]:
            for method in ["get", "post"]:
                with self.subTest(name=name, method=method):
                    self.assertRedirects(
                        getattr(self.client, method)(reverse("accounts:" + name)),
                        reverse("books:index"),
                    )

    def test_update_own_data_and_exclude_privileges(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("accounts:update"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("password", response.context["form"].fields)
        self.assertNotIn("is_staff", response.context["form"].fields)
        data = self.signup_data(email="changed@example.com", is_staff="on", is_superuser="on")
        self.assertRedirects(
            self.client.post(reverse("accounts:update"), data), reverse("books:index")
        )
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.email, "changed@example.com")
        self.assertFalse(self.owner.is_staff)
        self.assertFalse(self.owner.is_superuser)
        self.other.refresh_from_db()
        self.assertEqual(self.other.email, "")

    def test_invalid_update_preserves_data(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("accounts:update"), self.signup_data(email="bad", age=-1)
        )
        self.assertTrue(response.context["form"].errors)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.email, "")

    def test_profile_image_upload_and_display(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            data = BytesIO()
            Image.new("RGB", (2, 2)).save(data, format="PNG")
            upload = SimpleUploadedFile("avatar.png", data.getvalue(), content_type="image/png")
            self.client.force_login(self.owner)
            response = self.client.post(
                reverse("accounts:update"), self.signup_data(profile_image=upload)
            )
            self.assertRedirects(response, reverse("books:index"))
            self.owner.refresh_from_db()
            self.assertTrue(self.owner.profile_image.storage.exists(self.owner.profile_image.name))
            self.assertContains(
                self.client.get(reverse("accounts:profile", args=[self.owner.pk])),
                self.owner.profile_image.url,
            )

    def test_follow_toggle_and_no_self_follow(self):
        self.client.force_login(self.owner)
        url = reverse("accounts:follow", args=[self.other.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(
            self.client.post(url), reverse("accounts:profile", args=[self.other.pk])
        )
        self.assertTrue(self.owner.followings.filter(pk=self.other.pk).exists())
        self.assertFalse(self.other.followings.filter(pk=self.owner.pk).exists())
        self.assertContains(
            self.client.get(reverse("accounts:profile", args=[self.other.pk])), "언팔로우"
        )
        self.client.post(url)
        self.assertFalse(self.owner.followings.exists())
        self.client.post(reverse("accounts:follow", args=[self.owner.pk]))
        self.assertFalse(self.owner.followings.exists())

    def test_change_password_keeps_session(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("accounts:change_password")).status_code, 200)
        url = reverse("accounts:change_password")
        self.assertTrue(
            self.client.post(
                url,
                {
                    "old_password": "wrong",
                    "new_password1": "NextPass739!",
                    "new_password2": "NextPass739!",
                },
            )
            .context["form"]
            .errors
        )
        self.assertRedirects(
            self.client.post(
                url,
                {
                    "old_password": "InitialPass739!",
                    "new_password1": "NextPass739!",
                    "new_password2": "NextPass739!",
                },
            ),
            reverse("books:index"),
        )
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password("NextPass739!"))
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.owner.pk)
        self.assertEqual(self.client.get(reverse("accounts:update")).status_code, 200)

    def test_delete_account_and_session(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("accounts:delete")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("accounts:delete")), reverse("books:index"))
        self.assertFalse(User.objects.filter(pk=self.owner.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.other.pk).exists())
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_login_required_and_http_methods(self):
        for name, args, method in [
            ("update", [], "get"),
            ("delete", [], "post"),
            ("change_password", [], "get"),
            ("follow", [self.other.pk], "post"),
        ]:
            with self.subTest(name=name):
                self.assertEqual(
                    getattr(self.client, method)(
                        reverse("accounts:" + name, args=args)
                    ).status_code,
                    302,
                )
        self.assertEqual(
            self.client.post(reverse("accounts:profile", args=[self.owner.pk])).status_code, 405
        )
        for name in ["login", "signup"]:
            self.assertEqual(self.client.put(reverse("accounts:" + name)).status_code, 405)
        self.assertEqual(
            self.client.get(reverse("accounts:profile", args=[99999])).status_code, 404
        )

    def test_csrf_enforced_for_signup_and_follow(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(
            client.post(reverse("accounts:signup"), self.signup_data()).status_code, 403
        )
        client.force_login(self.owner)
        url = reverse("accounts:follow", args=[self.other.pk])
        self.assertEqual(client.post(url).status_code, 403)
        client.get(reverse("accounts:profile", args=[self.other.pk]))
        self.assertEqual(
            client.post(url, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value).status_code, 302
        )
