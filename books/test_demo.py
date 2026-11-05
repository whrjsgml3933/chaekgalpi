from io import StringIO
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from .models import Book, Thread, Comment


@override_settings(DEBUG=True)
class DemoCommandTests(TestCase):
    def test_demo_is_idempotent_and_preserves_password(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        user = get_user_model().objects.get(username="demo_reader")
        password_hash = user.password
        self.assertIn("Temporary local password:", output.getvalue())
        call_command("seed_demo", stdout=StringIO())
        user.refresh_from_db()
        self.assertEqual(user.password, password_hash)
        self.assertEqual(Book.objects.count(), 3)
        self.assertEqual(Thread.objects.count(), 1)
        self.assertEqual(Comment.objects.count(), 1)

    def test_existing_non_demo_user_is_not_modified(self):
        user = get_user_model().objects.create_user(
            username="demo_reader", password="ExistingPass739!"
        )
        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())
        user.refresh_from_db()
        self.assertTrue(user.check_password("ExistingPass739!"))
        self.assertFalse(Book.objects.exists())

    @override_settings(DEBUG=False)
    def test_demo_is_disabled_outside_debug(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())
        self.assertFalse(get_user_model().objects.exists())
