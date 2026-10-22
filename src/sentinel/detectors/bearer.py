"""Detect token values in literal Authorization: Bearer headers."""

import re

from sentinel.core.findings import Finding


_HEADERS = re.compile(
    # HTTP field names use tchar, including punctuation such as '.' and '+'.
    r"(?<![!#$%&'*+.^_`|~0-9A-Za-z-])Authorization[ \t]*:[ \t]*Bearer[ \t]+"
    r"(?P<token>[A-Za-z0-9._~+/-]+=*)"
    r'''(?=$|[\s"',;{}\[\]])''',
    re.IGNORECASE | re.ASCII,
)


def scan(text: str) -> list[Finding]:
    return [
        Finding(
            rule_id="BEARER_TOKEN",
            category="credential",
            start=match.start("token"),
            end=match.end("token"),
            severity="high",
            explanation="Token Bearer en un encabezado Authorization.",
        )
        for match in _HEADERS.finditer(text)
    ]
