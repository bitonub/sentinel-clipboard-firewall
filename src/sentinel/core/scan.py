from dataclasses import replace

from sentinel.core.findings import Finding
from sentinel.detectors.bearer import scan as scan_bearers
from sentinel.detectors.password import scan as scan_passwords
from sentinel.detectors.postgres import analyze as analyze_postgres
from sentinel.detectors.private_ipv4 import scan as scan_ipv4


def scan(text: str) -> list[Finding]:
    postgres, url_spans = analyze_postgres(text)
    generic = scan_passwords(text) + scan_bearers(text) + scan_ipv4(text)
    generic.sort(key=lambda finding: finding.start)
    candidates = list(postgres)
    url_index = 0
    for finding in generic:
        while url_index < len(url_spans) and url_spans[url_index][1] <= finding.start:
            url_index += 1
        # Suppress generic matches starting inside a credential-bearing URL.
        # A value starting at/before it must cover the entire URL, even when
        # the password grammar stopped early at a comma or semicolon.
        if url_index < len(url_spans):
            url_start = url_spans[url_index][0]
            if url_start < finding.start:
                continue
            overlap_index = url_index
            while overlap_index < len(url_spans) and url_spans[overlap_index][0] < finding.end:
                finding = replace(finding, end=max(finding.end, url_spans[overlap_index][1]))
                overlap_index += 1
        candidates.append(finding)
    # Prefer the enclosing value; for equal spans, credentials precede IPv4.
    candidates.sort(key=lambda finding: (
        finding.start, -finding.end, finding.rule_id != "PASSWORD_ASSIGNMENT"
    ))
    findings = []
    for finding in candidates:
        if findings and finding.start < findings[-1].end:
            # Contained intervals are already covered. Partial intersections
            # must extend coverage rather than silently lose a secret suffix.
            if finding.end > findings[-1].end:
                findings[-1] = replace(findings[-1], end=finding.end)
            continue
        findings.append(finding)
    return findings
