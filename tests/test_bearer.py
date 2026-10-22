from dataclasses import asdict
import json
import unittest

from sentinel.core.sanitize import sanitize
from sentinel.core.scan import scan as scan_all
from sentinel.detectors.bearer import scan


class BearerTests(unittest.TestCase):
    def test_case_spacing_and_token_positions(self):
        for header in ("Authorization: Bearer ", "AUTHORIZATION:\tBEARER\t", "authorization :  bEaReR   "):
            with self.subTest(header=header):
                text = f'α "{header}Synthetic-._~+/42=="; tail=ok\r\n'
                findings = scan(text)
                self.assertEqual(len(findings), 1)
                finding = findings[0]
                self.assertEqual(text[finding.start:finding.end], "Synthetic-._~+/42==")
                self.assertEqual(finding.start, text.index("Synthetic"))
                self.assertEqual(finding.category, "credential")
                self.assertEqual(finding.severity, "high")
                self.assertNotIn("Synthetic-._~+/42==", json.dumps(asdict(finding)))
                expected = f'α "{header}[BEARER_TOKEN_1]"; tail=ok\r\n'
                self.assertEqual(sanitize(text), expected)
                self.assertEqual(sanitize(expected), expected)

    def test_empty_incomplete_and_other_headers(self):
        for text in (
            "Authorization", "Authorization:", "Authorization: Bearer",
            "Authorization: Bearer \t", "Authorization: Bearer \r\nX-Test: synthetic",
            'Authorization: Bearer ""', "Authorization: Basic Synthetic42",
            "X-Authorization: Bearer Synthetic42", "Authorization: BearerSynthetic42",
            "Authorization: Bearer synthetic!invalid",
            "Authorization: Bearer [BEARER_TOKEN_1]",
        ):
            with self.subTest(text=text):
                self.assertEqual(scan(text), [])
                self.assertEqual(sanitize(text), text)

    def test_http_field_name_boundary(self):
        for separator in "!#$%&'*+-.^_`|~aZ09":
            text = f"X{separator}Authorization: Bearer Synthetic42"
            with self.subTest(text=text):
                self.assertEqual(scan(text), [])
                self.assertEqual(scan_all(text), [])
                self.assertEqual(sanitize(text), text)
                self.assertEqual(sanitize(sanitize(text)), text)

        text = "Authorization: Bearer Synthetic42"
        self.assertEqual(len(scan(text)), 1)
        self.assertEqual(sanitize(text), "Authorization: Bearer [BEARER_TOKEN_1]")

    def test_repetition_reservation_and_operation_local_labels(self):
        text = (
            "Authorization: Bearer Synthetic42\n"
            "Authorization: Bearer [BEARER_TOKEN_1]\n"
            "authorization: bearer Synthetic42\n"
            "Authorization: Bearer Other42\n"
            "note=[BEARER_TOKEN_3] tail=ok"
        )
        expected = (
            "Authorization: Bearer [BEARER_TOKEN_2]\n"
            "Authorization: Bearer [BEARER_TOKEN_1]\n"
            "authorization: bearer [BEARER_TOKEN_2]\n"
            "Authorization: Bearer [BEARER_TOKEN_4]\n"
            "note=[BEARER_TOKEN_3] tail=ok"
        )
        self.assertEqual(sanitize(text), expected)
        self.assertEqual(sanitize(expected), expected)
        self.assertEqual(sanitize("Authorization: Bearer Other42"), "Authorization: Bearer [BEARER_TOKEN_1]")

    def test_ipv4_and_password_overlaps(self):
        text = (
            'host=10.0.0.1 Authorization: Bearer 10.0.0.1\n'
            'password="Authorization: Bearer 192.168.1.2"\n'
            'pwd=synthetic Authorization: Bearer Synthetic42 tail=ok'
        )
        expected = (
            'host=[PRIVATE_IP_1] Authorization: Bearer [BEARER_TOKEN_1]\n'
            'password="[PASSWORD_1]"\n'
            'pwd=[PASSWORD_2] Authorization: Bearer [BEARER_TOKEN_2] tail=ok'
        )
        self.assertEqual(sanitize(text), expected)
        self.assertEqual(sanitize(expected), expected)
        findings = scan_all(text)
        self.assertEqual(len(findings), 5)
        self.assertTrue(all(a.end <= b.start for a, b in zip(findings, findings[1:])))
        self.assertEqual(sanitize('pwd="[BEARER_TOKEN_1]"'), 'pwd="[BEARER_TOKEN_1]"')


if __name__ == "__main__":
    unittest.main()
