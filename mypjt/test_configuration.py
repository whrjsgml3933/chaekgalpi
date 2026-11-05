import os
import subprocess
import sys
from pathlib import Path
from django.test import SimpleTestCase


class EnvironmentConfigurationTests(SimpleTestCase):
    def run_settings(self, overrides, assertions=""):
        env = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}
        env.update(PYTHON_DOTENV_DISABLED="1", AI_ENABLED="false")
        env.update(overrides)
        return subprocess.run(
            [sys.executable, "-c", "from mypjt import settings as s; " + assertions],
            cwd=Path(__file__).resolve().parent.parent,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_local_defaults_need_no_secret_or_ai_key(self):
        result = self.run_settings(
            {},
            "assert s.DEBUG; assert len(s.SECRET_KEY) >= 50; assert 'localhost' in s.ALLOWED_HOSTS",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_non_debug_mode_requires_secret(self):
        result = self.run_settings({"DJANGO_DEBUG": "false", "DJANGO_ALLOWED_HOSTS": "example.com"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", result.stderr)

    def test_non_debug_mode_requires_explicit_hosts(self):
        for hosts in ["", "*"]:
            with self.subTest(hosts=hosts):
                result = self.run_settings(
                    {
                        "DJANGO_DEBUG": "false",
                        "DJANGO_SECRET_KEY": "test-configuration-secret-" * 3,
                        "DJANGO_ALLOWED_HOSTS": hosts,
                    }
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("DJANGO_ALLOWED_HOSTS", result.stderr)

    def test_non_debug_mode_enables_secure_cookies_and_redirect(self):
        result = self.run_settings(
            {
                "DJANGO_DEBUG": "false",
                "DJANGO_SECRET_KEY": "test-configuration-secret-" * 3,
                "DJANGO_ALLOWED_HOSTS": "example.com",
            },
            "assert not s.DEBUG; assert s.ALLOWED_HOSTS == ['example.com']; assert s.SESSION_COOKIE_SECURE; assert s.CSRF_COOKIE_SECURE; assert s.SECURE_SSL_REDIRECT",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
