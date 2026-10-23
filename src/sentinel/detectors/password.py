"""Recognize simple password assignments, without interpreting their values."""

import re

from sentinel.core.findings import Finding


_KEY = r"(?:password|passwd|pwd)"
_ASSIGNMENTS = re.compile(
    rf"(?<![\w.-])(?:{_KEY}|\"{_KEY}\"|'{_KEY}')[ \t]*[=:]"
    # Whitespace followed by another assignment denotes an empty value.
    r"""(?![ \t]+(?:[\w.-]+|"[^"\r\n]+"|'[^'\r\n]+')[ \t]*[=:])"""
    r"[ \t]*"
    r'''(?:"(?P<double>(?:\\[^\r\n]|[^"\\\r\n])*)"'''
    r"""|'(?P<single>(?:\\[^\r\n]|[^'\\\r\n])*)'"""
    r'''|(?P<bare>(?:\$\{[^{}\s]*\}|[^\s,;'"{}\[\]])+))''',
    re.IGNORECASE,
)
_PLACEHOLDER = re.compile(
    r"(?:\$\{[^{}\s]+\}|\$[A-Za-z_][A-Za-z_0-9]*|"
    r"\[(?:PASSWORD|PRIVATE_IP|BEARER_TOKEN|POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_URL)_[0-9]+\])"
)


def scan(text: str) -> list[Finding]:
    findings = []
    for match in _ASSIGNMENTS.finditer(text):
        group = match.lastgroup
        value = match.group(group)
        if not value or value.isspace() or _PLACEHOLDER.fullmatch(value):
            continue
        findings.append(
            Finding(
                rule_id="PASSWORD_ASSIGNMENT",
                category="credential",
                start=match.start(group),
                end=match.end(group),
                severity="high",
                explanation="Asignación de un posible valor de contraseña.",
            )
        )
    return findings
