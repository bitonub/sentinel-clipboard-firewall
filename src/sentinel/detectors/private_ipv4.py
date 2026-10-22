"""Detect RFC 1918 IPv4 addresses in untrusted text."""

import ipaddress
import re

from sentinel.core.findings import Finding


_CANDIDATES = re.compile(r"(?<![\w.])[0-9.]+(?![\w.])")
_IPV6_CONTEXTS = re.compile(r"[0-9A-Fa-f:.]+")
_NETWORKS = tuple(
    ipaddress.IPv4Network(cidr)
    for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)


def scan(text: str) -> list[Finding]:
    findings = []
    ipv6_spans = []
    for context in _IPV6_CONTEXTS.finditer(text):
        if ":" not in context.group() or "." not in context.group():
            continue
        try:
            ipaddress.IPv6Address(context.group())
        except ipaddress.AddressValueError:
            continue
        ipv6_spans.append(context.span())

    ipv6_index = 0
    for match in _CANDIDATES.finditer(text):
        while ipv6_index < len(ipv6_spans) and ipv6_spans[ipv6_index][1] <= match.start():
            ipv6_index += 1
        if ipv6_index < len(ipv6_spans):
            ipv6_start, ipv6_end = ipv6_spans[ipv6_index]
            if ipv6_start <= match.start() and match.end() <= ipv6_end:
                continue
        try:
            address = ipaddress.IPv4Address(match.group())
        except ipaddress.AddressValueError:
            continue
        if any(address in network for network in _NETWORKS):
            findings.append(
                Finding(
                    rule_id="RFC1918_IPV4",
                    category="infrastructure",
                    start=match.start(),
                    end=match.end(),
                    severity="informational",
                    explanation="Dirección IPv4 en un rango privado RFC 1918.",
                )
            )
    return findings
