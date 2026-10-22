import unittest

from sentinel.core.sanitize import sanitize
from sentinel.detectors.private_ipv4 import scan


class PrivateIPv4Tests(unittest.TestCase):
    def test_range_boundaries(self):
        inside = (
            "10.0.0.0 10.255.255.255 172.16.0.0 172.31.255.255 "
            "192.168.0.0 192.168.255.255"
        )
        outside = (
            "9.255.255.255 11.0.0.0 172.15.255.255 "
            "172.32.0.0 192.167.255.255 192.169.0.0"
        )
        self.assertEqual(len(scan(inside)), 6)
        self.assertEqual(scan(outside), [])

    def test_public_invalid_and_malformed(self):
        text = (
            "8.8.8.8 127.0.0.1 169.254.1.1 10.0.0.256 "
            "10.0.0.1.2 10.0.0.1.2x 10.0.0.1.abc "
            "999.10.0.0.1 10.0.0.1x "
            "x10.0.0.1 010.0.0.1 10..0.1"
        )
        self.assertEqual(scan(text), [])
        self.assertEqual(sanitize(text), text)

    def test_ipv6_embedded_ipv4_and_colon_context(self):
        ipv6 = "::ffff:10.0.0.1 2001:db8::10.0.0.1"
        self.assertEqual(scan(ipv6), [])
        self.assertEqual(sanitize(ipv6), ipv6)

        ordinary = "10.0.0.1 host:10.0.0.1"
        findings = scan(ordinary)
        self.assertEqual(len(findings), 2)
        self.assertEqual(sanitize(ordinary), "[PRIVATE_IP_1] host:[PRIVATE_IP_1]")

    def test_positions_metadata_repetition_and_idempotence(self):
        text = "α host=10.20.30.40 peer=10.20.30.40 other=192.168.1.2!"
        findings = scan(text)
        self.assertEqual(len(findings), 3)
        first = text.index("10.20.30.40")
        second = text.index("10.20.30.40", first + 1)
        third = text.index("192.168.1.2")
        self.assertEqual(
            [(f.start, f.end) for f in findings],
            [(first, first + 11), (second, second + 11), (third, third + 11)],
        )
        self.assertEqual(findings[0].rule_id, "RFC1918_IPV4")
        self.assertEqual(findings[0].category, "infrastructure")
        self.assertEqual(findings[0].severity, "informational")
        self.assertTrue(findings[0].explanation)
        self.assertFalse(hasattr(findings[0], "value"))
        result = "α host=[PRIVATE_IP_1] peer=[PRIVATE_IP_1] other=[PRIVATE_IP_2]!"
        self.assertEqual(sanitize(text), result)
        self.assertEqual(sanitize(result), result)
        self.assertEqual(sanitize("10.0.0.1"), "[PRIVATE_IP_1]")


if __name__ == "__main__":
    unittest.main()
