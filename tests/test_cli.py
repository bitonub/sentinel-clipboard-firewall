import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


def run_cli(command: str, data: bytes) -> subprocess.CompletedProcess[bytes]:
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    return subprocess.run(
        [sys.executable, "-m", "sentinel", command],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )


class CliTests(unittest.TestCase):
    def test_scan(self):
        result = run_cli("scan", b"host=10.20.30.40 public=8.8.8.8")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        findings = json.loads(result.stdout)
        self.assertEqual(len(findings), 1)
        self.assertEqual((findings[0]["start"], findings[0]["end"]), (5, 16))
        self.assertNotIn(b"10.20.30.40", result.stdout)

    def test_sanitize(self):
        result = run_cli("sanitize", b"host=10.20.30.40 peer=10.20.30.40")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"host=[PRIVATE_IP_1] peer=[PRIVATE_IP_1]")
        self.assertEqual(result.stderr, b"")

    def test_password_scan_and_sanitize(self):
        text = b"password=SyntheticSecret42 pwd=SyntheticSecret42"
        result = run_cli("scan", text)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        findings = json.loads(result.stdout)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0]["rule_id"], "PASSWORD_ASSIGNMENT")
        self.assertEqual((findings[0]["start"], findings[0]["end"]), (9, 26))
        self.assertNotIn(b"SyntheticSecret42", result.stdout)
        result = run_cli("sanitize", text)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(result.stdout, b"password=[PASSWORD_1] pwd=[PASSWORD_1]")

    def test_bearer_scan_and_sanitize(self):
        text = b"Authorization: Bearer SyntheticBearer42\n"
        result = run_cli("scan", text)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        findings = json.loads(result.stdout)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "BEARER_TOKEN")
        self.assertEqual((findings[0]["start"], findings[0]["end"]), (22, 39))
        self.assertNotIn(b"SyntheticBearer42", result.stdout)
        result = run_cli("sanitize", text)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(result.stdout, b"Authorization: Bearer [BEARER_TOKEN_1]\n")

    def test_input_size_boundary(self):
        exact = run_cli("sanitize", b"a" * (1024 * 1024))
        self.assertEqual(exact.returncode, 0)
        self.assertEqual(len(exact.stdout), 1024 * 1024)
        over = run_cli("sanitize", b"a" * (1024 * 1024 + 1))
        self.assertNotEqual(over.returncode, 0)
        self.assertEqual(over.stdout, b"")
        self.assertIn(b"1 MiB", over.stderr)

    def test_errors_do_not_echo_input(self):
        marker = b"SECRET_SYNTHETIC_MARKER"
        invalid = run_cli("scan", marker + b"\xff")
        self.assertNotEqual(invalid.returncode, 0)
        self.assertEqual(invalid.stdout, b"")
        self.assertNotIn(marker, invalid.stderr)
        over = run_cli("scan", marker + b"x" * (1024 * 1024))
        self.assertNotEqual(over.returncode, 0)
        self.assertEqual(over.stdout, b"")
        self.assertNotIn(marker, over.stderr)


if __name__ == "__main__":
    unittest.main()
