"""Locate userinfo spans in PostgreSQL URLs without connecting to a server."""

import re

from sentinel.core.findings import Finding


_URLS = re.compile(r'''(?<![\w+.-])postgres(?:ql)?://[^\s<>"']*''', re.IGNORECASE)
_COMPONENT = re.compile(r"(?:[A-Za-z0-9._~!$&()*+,;=:-]|%[0-9A-Fa-f]{2})*")
_PLACEHOLDER = re.compile(
    r"\[(?:POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_URL|PASSWORD|BEARER_TOKEN|PRIVATE_IP)_[0-9]+\]"
)


def analyze(text: str) -> tuple[list[Finding], list[tuple[int, int]]]:
    """Return findings and credential-bearing candidate spans without values."""
    findings = []
    url_spans = []
    for match in _URLS.finditer(text):
        candidate = match.group()
        scheme_end = candidate.index("://") + 3
        authority_end = re.search(r"[/?#]", candidate[scheme_end:])
        authority_end = scheme_end + authority_end.start() if authority_end else len(candidate)
        authority = candidate[scheme_end:authority_end]
        if "@" not in authority:
            continue

        # Protect the candidate before validation. Host/port validity does not
        # affect the boundaries of an unambiguous userinfo component.
        url_spans.append(match.span())
        userinfo = authority.split("@", 1)[0]
        user, separator, password = userinfo.partition(":")
        ambiguous = (
            authority.count("@") != 1
            or any(ord(char) < 32 or ord(char) == 127 for char in candidate)
            or not all(_COMPONENT.fullmatch(value) or _PLACEHOLDER.fullmatch(value)
                       for value in (user, password))
        )
        if ambiguous:
            findings.append(Finding(
                "POSTGRES_URL", "credential", match.start(), match.end(), "high",
                "URL PostgreSQL con userinfo ambiguo; se oculta la candidata completa.",
            ))
            continue
        offset = match.start() + scheme_end
        for value, start, rule_id, category, explanation in (
            (user, offset, "POSTGRES_USER", "database_user", "Usuario en userinfo de una URL PostgreSQL."),
            (password, offset + len(user) + len(separator), "POSTGRES_PASSWORD", "database_password",
             "Contraseña en userinfo de una URL PostgreSQL."),
        ):
            if value and not _PLACEHOLDER.fullmatch(value):
                findings.append(Finding(rule_id, category, start, start + len(value), "high", explanation))
    return findings, url_spans


def scan(text: str) -> list[Finding]:
    return analyze(text)[0]
