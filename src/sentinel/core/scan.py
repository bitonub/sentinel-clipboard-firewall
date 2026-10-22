from sentinel.core.findings import Finding
from sentinel.detectors.password import scan as scan_passwords
from sentinel.detectors.private_ipv4 import scan as scan_ipv4


def scan(text: str) -> list[Finding]:
    passwords = scan_passwords(text)
    findings = list(passwords)
    password_index = 0
    for finding in scan_ipv4(text):
        while password_index < len(passwords) and passwords[password_index].end <= finding.start:
            password_index += 1
        if password_index < len(passwords) and passwords[password_index].start < finding.end:
            continue
        findings.append(finding)
    return sorted(findings, key=lambda finding: finding.start)
