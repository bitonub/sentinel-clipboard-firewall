from dataclasses import asdict
import json
import unittest

from sentinel.core.sanitize import sanitize
from sentinel.core.scan import scan as scan_all
from sentinel.detectors.postgres import scan


class PostgresTests(unittest.TestCase):
    def test_schemes_spans_and_remaining_text(self):
        for scheme in ("postgres", "postgresql", "POSTGRESQL"):
            text = f'α url="{scheme}://synthetic_user:synthetic_secret@db.example:5432/app?sslmode=require#part" tail=ok'
            expected = f'α url="{scheme}://[POSTGRES_USER_1]:[POSTGRES_PASSWORD_1]@db.example:5432/app?sslmode=require#part" tail=ok'
            with self.subTest(scheme=scheme):
                findings = scan_all(text)
                self.assertEqual(len(findings), 2)
                self.assertEqual([text[f.start:f.end] for f in findings], ["synthetic_user", "synthetic_secret"])
                self.assertEqual(findings[0].start, text.index("synthetic_user"))
                serialized = json.dumps([asdict(f) for f in findings])
                self.assertNotIn("synthetic_user", serialized)
                self.assertNotIn("synthetic_secret", serialized)
                self.assertEqual(sanitize(text), expected)
                self.assertEqual(sanitize(expected), expected)

    def test_percent_encoded_userinfo(self):
        text = "postgres://user%40example:p%3Ass%2Fword%25@db.example/app"
        expected = "postgres://[POSTGRES_USER_1]:[POSTGRES_PASSWORD_1]@db.example/app"
        self.assertEqual(sanitize(text), expected)
        self.assertEqual(sanitize(expected), expected)
        self.assertEqual(len(scan(text)), 2)
        serialized = json.dumps([asdict(f) for f in scan_all(text)])
        self.assertNotIn("user%40example", serialized)
        self.assertNotIn("p%3Ass%2Fword%25", serialized)

    def test_absent_credentials_and_malformed_urls(self):
        for text in (
            "postgres://db.example/app", "postgresql://db.example:5432/app",
            "postgres://", "notpostgres://user:secret@db/app",
        ):
            with self.subTest(text=text):
                self.assertEqual(scan(text), [])
                self.assertEqual(sanitize(text), text)

    def test_identifiable_userinfo_with_malformed_or_multiple_hosts(self):
        for suffix in (
            "", "db:invalid/app", "db:65536/app", "db:/app", "[::1/app",
            "[invalid]/app", "[::1]garbage/app", "one.example,two.example/app",
            "10.0.0.1:5432,10.0.0.2:5432/app",
        ):
            text = f"α postgres://pwd:synthetic@{suffix} tail=ok"
            expected = f"α postgres://[POSTGRES_USER_1]:[POSTGRES_PASSWORD_1]@{suffix} tail=ok"
            with self.subTest(suffix=suffix):
                findings = scan_all(text)
                self.assertEqual([f.rule_id for f in findings], ["POSTGRES_USER", "POSTGRES_PASSWORD"])
                serialized = json.dumps([asdict(f) for f in findings])
                self.assertNotIn('"pwd"', serialized)
                self.assertNotIn("synthetic", serialized)
                self.assertEqual(sanitize(text), expected)
                self.assertEqual(sanitize(expected), expected)

    def test_ambiguous_userinfo_redacts_whole_candidate(self):
        for url in (
            "postgres://SyntheticUser42:SyntheticSecret42@one@two/app",
            "postgres://SyntheticUser42%ZZ:SyntheticSecret42@db/app",
            "postgres://SyntheticUser42:SyntheticSecret42%2@db/app",
            "postgres://SyntheticUser42:SyntheticSecret42@db\x00/app",
        ):
            text = f'α url="{url}" tail=ok'
            with self.subTest(url=url):
                findings = scan_all(text)
                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0].rule_id, "POSTGRES_URL")
                self.assertEqual(text[findings[0].start:findings[0].end], url)
                serialized = json.dumps([asdict(f) for f in findings])
                self.assertNotIn("SyntheticUser42", serialized)
                self.assertNotIn("SyntheticSecret42", serialized)
                expected = 'α url="[POSTGRES_URL_1]" tail=ok'
                self.assertEqual(sanitize(text), expected)
                self.assertEqual(sanitize(expected), expected)

        url = "postgres://user:secret@one@two/app"
        text = f"note=[POSTGRES_URL_1] {url} {url}"
        expected = "note=[POSTGRES_URL_1] [POSTGRES_URL_2] [POSTGRES_URL_2]"
        self.assertEqual(sanitize(text), expected)
        self.assertEqual(sanitize(expected), expected)
        self.assertEqual(sanitize(f'pwd="{url}"'), 'pwd="[PASSWORD_1]"')

    def test_no_userinfo_still_allows_ipv4(self):
        text = "postgres://10.0.0.1/app postgres://10.0.0.2:5432,10.0.0.1:5432/app"
        expected = "postgres://[PRIVATE_IP_1]/app postgres://[PRIVATE_IP_2]:5432,[PRIVATE_IP_1]:5432/app"
        self.assertEqual(scan(text), [])
        self.assertEqual(sanitize(text), expected)
        self.assertEqual(sanitize(expected), expected)

    def test_partial_password_overlap_covers_entire_url(self):
        for url in (
            "postgres://user:synthetic,tail@db.example/app",
            "postgres://user:synthetic,tail@db:bad/app",
            "postgres://user:synthetic,tail@one.example,two.example/app",
            "postgres://user%ZZ:synthetic,tail@db/app",
        ):
            text = f"password=prefix/{url} suffix=ok"
            with self.subTest(url=url):
                findings = scan_all(text)
                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0].rule_id, "PASSWORD_ASSIGNMENT")
                self.assertEqual(text[findings[0].start:findings[0].end], f"prefix/{url}")
                serialized = json.dumps([asdict(f) for f in findings])
                self.assertNotIn("synthetic", serialized)
                self.assertNotIn("tail", serialized)
                expected = "password=[PASSWORD_1] suffix=ok"
                self.assertEqual(sanitize(text), expected)
                self.assertEqual(sanitize(expected), expected)

    def test_optional_empty_components_and_ipv6_host(self):
        for text, expected in (
            ("postgres://synthetic@db/app", "postgres://[POSTGRES_USER_1]@db/app"),
            ("postgres://synthetic:@db/app", "postgres://[POSTGRES_USER_1]:@db/app"),
            ("postgres://:synthetic@db/app", "postgres://:[POSTGRES_PASSWORD_1]@db/app"),
            ("postgres://user:secret@[2001:db8::1]:5432/app", "postgres://[POSTGRES_USER_1]:[POSTGRES_PASSWORD_1]@[2001:db8::1]:5432/app"),
        ):
            with self.subTest(text=text):
                self.assertEqual(sanitize(text), expected)
                self.assertEqual(sanitize(expected), expected)

    def test_repetitions_and_reserved_labels(self):
        text = (
            "postgres://user:secret@db/app postgres://[POSTGRES_USER_1]:[POSTGRES_PASSWORD_2]@db/app "
            "postgresql://user:secret@other/app postgres://other:different@db/app"
        )
        expected = (
            "postgres://[POSTGRES_USER_2]:[POSTGRES_PASSWORD_1]@db/app "
            "postgres://[POSTGRES_USER_1]:[POSTGRES_PASSWORD_2]@db/app "
            "postgresql://[POSTGRES_USER_2]:[POSTGRES_PASSWORD_1]@other/app "
            "postgres://[POSTGRES_USER_3]:[POSTGRES_PASSWORD_3]@db/app"
        )
        self.assertEqual(sanitize(text), expected)
        self.assertEqual(sanitize(expected), expected)
        self.assertEqual(sanitize("postgres://other:different@db/app"), "postgres://[POSTGRES_USER_1]:[POSTGRES_PASSWORD_1]@db/app")

    def test_overlaps_and_existing_rules(self):
        text = (
            'postgres://pwd:10.0.0.1@192.168.1.2:5432/app?password=keep\n'
            'password="postgres://user:secret@db/app"\n'
            'pwd=standalone Authorization: Bearer Synthetic42 host=10.0.0.1'
        )
        expected = (
            'postgres://[POSTGRES_USER_1]:[POSTGRES_PASSWORD_1]@192.168.1.2:5432/app?password=keep\n'
            'password="[PASSWORD_1]"\n'
            'pwd=[PASSWORD_2] Authorization: Bearer [BEARER_TOKEN_1] host=[PRIVATE_IP_1]'
        )
        findings = scan_all(text)
        self.assertEqual(len(findings), 6)
        self.assertTrue(all(a.end <= b.start for a, b in zip(findings, findings[1:])))
        self.assertEqual(sanitize(text), expected)
        self.assertEqual(sanitize(expected), expected)
        self.assertEqual(sanitize('pwd="[POSTGRES_PASSWORD_1]"'), 'pwd="[POSTGRES_PASSWORD_1]"')


if __name__ == "__main__":
    unittest.main()
