import os
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings


class SeedCommandSafetyTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_seed_is_disabled_when_debug_is_false_even_with_opt_in(self):
        with patch.dict(os.environ, {"ITSM_ALLOW_DEMO_SEED": "1"}):
            with self.assertRaisesMessage(CommandError, "disabled when DEBUG=False"):
                call_command("seed")

    @override_settings(DEBUG=True)
    def test_seed_requires_explicit_local_opt_in(self):
        with patch.dict(os.environ, {"ITSM_ALLOW_DEMO_SEED": ""}):
            with self.assertRaisesMessage(CommandError, "ITSM_ALLOW_DEMO_SEED=1"):
                call_command("seed")
