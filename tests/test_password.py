from dataclasses import asdict
import json
import unittest

from sentinel.core.sanitize import sanitize
from sentinel.core.scan import scan as scan_all
from sentinel.detectors.password import scan


class PasswordTests(unittest.TestCase):
    def test_names_separators_and_case(self):
        for name in ("password", "PASSWD", "PwD"):
            for separator in ("=", ":"):
                text = f"α {name} {separator}\tSynthetic-42!"
                with self.subTest(name=name, separator=separator):
                    findings = scan(text)
                    self.assertEqual(len(findings), 1)
                    finding = findings[0]
                    self.assertEqual(text[finding.start:finding.end], "Synthetic-42!")
                    self.assertEqual(sanitize(text), f"α {name} {separator}\t[PASSWORD_1]")
                    self.assertEqual(finding.category, "credential")
                    self.assertEqual(finding.severity, "high")
                    self.assertNotIn("Synthetic-42!", json.dumps(asdict(finding)))

    def test_quotes_and_rest_of_text(self):
        text = '''{"password": "synthetic phrase", 'passwd': 'other synthetic'}; pwd=third, next=ok'''
        expected = '''{"password": "[PASSWORD_1]", 'passwd': '[PASSWORD_2]'}; pwd=[PASSWORD_3], next=ok'''
        self.assertEqual(sanitize(text), expected)
        self.assertEqual(sanitize(expected), expected)

    def test_escaped_quotes(self):
        text = r'''password="synthetic\"value" passwd='other\'value' '''
        self.assertEqual(sanitize(text), '''password="[PASSWORD_1]" passwd='[PASSWORD_2]' ''')

    def test_empty_placeholder_and_unrelated_names(self):
        for text in (
            "password=", "passwd: \t", 'pwd=""', "password=''", 'pwd="   "',
            "password=\nother=value", "password=${PASSWORD}", 'pwd="${OTHER}"',
            "passwd=$SYNTHETIC", "pwd=[PASSWORD_1]", 'password="[PASSWORD_2]"',
            "db_password=value", "password_hint=value", "notpassword=value",
            "password.value=synthetic", "password value", 'pwd="unfinished',
        ):
            with self.subTest(text=text):
                self.assertEqual(scan(text), [])
                self.assertEqual(sanitize(text), text)

    def test_repetition_and_operation_local_labels(self):
        text = 'password=synthetic pwd="synthetic" passwd=other password=synthetic'
        expected = 'password=[PASSWORD_1] pwd="[PASSWORD_1]" passwd=[PASSWORD_2] password=[PASSWORD_1]'
        self.assertEqual(sanitize(text), expected)
        self.assertEqual(sanitize(expected), expected)
        self.assertEqual(sanitize("pwd=other"), "pwd=[PASSWORD_1]")

    def test_empty_value_does_not_consume_next_assignment(self):
        for text in (
            "password= passwd=${PASSWORD}",
            'password= pwd=""',
            'α password=\t "PASSWD" : "${PASSWORD}"; tail=ok',
            "password= host=synthetic; tail=ok",
        ):
            with self.subTest(text=text):
                self.assertEqual(scan(text), [])
                self.assertEqual(sanitize(text), text)
                self.assertEqual(sanitize(sanitize(text)), text)

        text = 'password= passwd=Synthetic42; pwd="key=value" tail=ok'
        expected = 'password= passwd=[PASSWORD_1]; pwd="[PASSWORD_2]" tail=ok'
        self.assertEqual(len(scan(text)), 2)
        self.assertEqual(sanitize(text), expected)
        self.assertEqual(sanitize(expected), expected)

    def test_existing_password_labels_are_reserved(self):
        text = 'password="[PASSWORD_1]" pwd=Synthetic42 passwd="Synthetic42" tail=ok'
        expected = 'password="[PASSWORD_1]" pwd=[PASSWORD_2] passwd="[PASSWORD_2]" tail=ok'
        self.assertEqual(sanitize(text), expected)
        self.assertEqual(sanitize(expected), expected)

        text = 'α pwd=first password=second passwd=first note=[PASSWORD_2] host=10.0.0.1'
        expected = 'α pwd=[PASSWORD_1] password=[PASSWORD_3] passwd=[PASSWORD_1] note=[PASSWORD_2] host=[PRIVATE_IP_1]'
        self.assertEqual(sanitize(text), expected)
        self.assertEqual(sanitize(expected), expected)
        self.assertEqual(sanitize("pwd=first"), "pwd=[PASSWORD_1]")

    def test_mixed_ipv4_and_overlapping_password(self):
        text = 'host=10.0.0.1 password="10.0.0.1 and 192.168.1.1" peer=192.168.1.1 pwd=10.0.0.1'
        expected = 'host=[PRIVATE_IP_1] password="[PASSWORD_1]" peer=[PRIVATE_IP_2] pwd=[PASSWORD_2]'
        self.assertEqual(sanitize(text), expected)
        self.assertEqual(sanitize(expected), expected)
        findings = scan_all(text)
        self.assertEqual(len(findings), 4)
        self.assertTrue(all(a.end <= b.start for a, b in zip(findings, findings[1:])))


if __name__ == "__main__":
    unittest.main()
