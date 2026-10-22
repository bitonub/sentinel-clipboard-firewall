from sentinel.core.findings import Finding
from sentinel.detectors.bearer import scan as scan_bearers
from sentinel.detectors.password import scan as scan_passwords
from sentinel.detectors.private_ipv4 import scan as scan_ipv4


def scan(text: str) -> list[Finding]:
    candidates = scan_passwords(text) + scan_bearers(text) + scan_ipv4(text)
    # Prefer the enclosing value; for equal spans, credentials precede IPv4.
    candidates.sort(key=lambda finding: (finding.start, -finding.end))
    findings = []
    for finding in candidates:
        if findings and finding.start < findings[-1].end:
            continue
        findings.append(finding)
    return findings
