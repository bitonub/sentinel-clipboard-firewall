"""Qt-free import and launch failure contracts."""

from contextlib import redirect_stderr
import builtins
import io
import unittest
from unittest.mock import patch


class GuiLauncherTests(unittest.TestCase):
    def test_launcher_and_cli_import_without_qt_and_missing_extra_error_is_safe(self):
        original_import = builtins.__import__

        def without_qt(name, *args, **kwargs):
            if name.startswith("PySide6"):
                raise ModuleNotFoundError("SyntheticPrivate", name="PySide6")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=without_qt):
            from sentinel.gui.app import main
            import sentinel.cli

            error = io.StringIO()
            with redirect_stderr(error):
                self.assertEqual(main(), 2)
        self.assertIn("[gui]", error.getvalue())
        self.assertNotIn("SyntheticPrivate", error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())
