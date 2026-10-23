import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import check_packages
from tools.run_tests import gate_errors


class CiGateTests(unittest.TestCase):
    def result(self, skipped=(), *, success=True, count=3):
        return SimpleNamespace(testsRun=count, wasSuccessful=lambda: success,
                               skipped=[(SimpleNamespace(id=lambda value=value: value), "missing Qt")
                                        for value in skipped])

    def test_cli_accepts_only_the_expected_gui_skips(self):
        self.assertEqual(gate_errors("cli", {"gui.a", "gui.b"}, 3,
                                     self.result(("gui.a", "gui.b"))), [])

    def test_gui_rejects_any_skip(self):
        self.assertTrue(gate_errors("gui", {"gui.a"}, 3, self.result(("gui.a",))))

    def test_cli_rejects_wrong_skips_even_when_count_matches(self):
        self.assertTrue(gate_errors("cli", {"gui.a"}, 3, self.result(("other.a",))))

    def test_cli_requires_all_expected_gui_skips(self):
        self.assertTrue(gate_errors("cli", {"gui.a", "gui.b"}, 3, self.result(("gui.a",))))

    def test_gui_requires_gui_test_discovery(self):
        self.assertTrue(gate_errors("gui", set(), 3, self.result()))

    def test_failures_fail_the_gate(self):
        self.assertTrue(gate_errors("gui", {"gui.a"}, 3, self.result(success=False)))

    def test_incomplete_execution_fails_the_gate(self):
        self.assertTrue(gate_errors("gui", {"gui.a"}, 3, self.result(count=2)))

    def test_gui_accepts_a_complete_run_without_skips(self):
        self.assertEqual(gate_errors("gui", {"gui.a"}, 3, self.result()), [])

    def test_smoke_preserves_isolation_and_exchanges_accented_utf8_json(self):
        fixture = '''
import json
import sys
assert sys.flags.isolated == 1
assert sys.flags.utf8_mode == 1
assert sys.stdout.encoding == "utf-8"
content = sys.stdin.buffer.read().decode("utf-8")
if sys.argv[1] == "sentinel-gui":
    sys.stderr.write("Install [gui].")
    raise SystemExit(2)
command = sys.argv[2]
if command == "sanitize":
    sys.stdout.write("password=[PASSWORD_1] pwd=[PASSWORD_1]")
else:
    if command == "scan":
        assert content.startswith("é ")
    rule = ("PASSWORD_ASSIGNMENT" if command == "scan" else
            "CF-PS-001" if "powershell" in sys.argv else "CF-BASH-001")
    print(json.dumps([{"rule_id": rule, "explanation": "Contraseña sintética"}],
                     ensure_ascii=False))
'''
        run = subprocess.run
        commands = []

        def checked_run(command, **kwargs):
            if command[1:4] == ["-m", "pip", "check"]:
                return subprocess.CompletedProcess(command, 0)
            self.assertEqual(command[:5], [sys.executable, "-I", "-X", "utf8", "-c"])
            self.assertNotIn("PYTHONPATH", kwargs["env"])
            self.assertNotIn("PYTHONHOME", kwargs["env"])
            self.assertEqual(kwargs["env"]["PYTHONIOENCODING"], "cp1252")
            self.assertEqual(kwargs["cwd"], outside)
            commands.append(command)
            result = run(command, **kwargs)
            if command[-1] != "sentinel-gui" and "sanitize" not in command[7:]:
                self.assertIn("Contraseña sintética".encode("utf-8"), result.stdout)
                self.assertEqual(json.loads(result.stdout)[0]["explanation"], "Contraseña sintética")
            return result

        with tempfile.TemporaryDirectory(prefix="sentinel-ci-utf8-") as directory:
            outside = Path(directory)
            with (patch.dict(os.environ, {"PYTHONPATH": directory, "PYTHONHOME": directory,
                                          "PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1252"}),
                  patch.object(check_packages, "SMOKE", fixture),
                  patch.object(check_packages.subprocess, "run", side_effect=checked_run),
                  contextlib.redirect_stdout(io.StringIO())):
                check_packages.smoke_cli(Path(sys.executable), outside)
        self.assertEqual(len(commands), 5)
