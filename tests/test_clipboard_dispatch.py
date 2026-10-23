"""Platform dispatch tests never invoke native clipboard implementations."""

import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from sentinel.adapters import clipboard


class ClipboardDispatchTests(unittest.TestCase):
    def test_dispatches_only_to_the_selected_injected_backend(self):
        for platform, selected, other in (("win32", "windows", "wayland"), ("linux", "wayland", "windows")):
            with self.subTest(platform=platform):
                expected = clipboard.ClipboardResult(True, 3)
                with (patch.object(clipboard.sys, "platform", platform),
                      patch(f"sentinel.adapters.{selected}.sanitize_clipboard", return_value=expected) as operation,
                      patch(f"sentinel.adapters.{other}.sanitize_clipboard", side_effect=AssertionError("Wrong backend")) as wrong):
                    self.assertEqual(clipboard.sanitize_clipboard(), expected)
                operation.assert_called_once_with()
                wrong.assert_not_called()

    def test_other_platforms_are_rejected_without_loading_a_backend(self):
        with patch.object(clipboard.sys, "platform", "darwin"):
            with self.assertRaises(clipboard.ClipboardError) as caught:
                clipboard.sanitize_clipboard()
        self.assertIn("no compatible", str(caught.exception))

    def test_import_is_deferred_even_on_windows_and_requires_no_qt(self):
        code = '''
import ctypes
import sys
def forbidden(*args, **kwargs):
    raise AssertionError("Native DLL loading forbidden")
ctypes.WinDLL = forbidden
import sentinel.cli
assert "PySide6" not in sys.modules
assert "sentinel.adapters.wayland" not in sys.modules
assert "sentinel.adapters.windows" not in sys.modules
import sentinel.adapters.windows
'''
        result = subprocess.run([sys.executable, "-I", "-X", "utf8", "-c", code],
                                capture_output=True, timeout=10, env=dict(os.environ), check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        self.assertEqual(result.stdout, b"")
