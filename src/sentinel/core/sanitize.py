import re

from sentinel.core.scan import scan


_PREFIXES = {
    "RFC1918_IPV4": "PRIVATE_IP",
    "PASSWORD_ASSIGNMENT": "PASSWORD",
    "BEARER_TOKEN": "BEARER_TOKEN",
    "POSTGRES_USER": "POSTGRES_USER",
    "POSTGRES_PASSWORD": "POSTGRES_PASSWORD",
    "POSTGRES_URL": "POSTGRES_URL",
}


def sanitize(text: str) -> str:
    pieces = []
    placeholders: dict[tuple[str, str], str] = {}
    counts: dict[str, int] = {}
    reserved_labels = set(re.findall(
        r"\[(?:PASSWORD|BEARER_TOKEN|POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_URL)_[0-9]+\]", text
    ))
    previous_end = 0
    for finding in scan(text):
        value = text[finding.start:finding.end]
        key = (finding.rule_id, value)
        if key not in placeholders:
            prefix = _PREFIXES[finding.rule_id]
            number = counts.get(prefix, 0) + 1
            while f"[{prefix}_{number}]" in reserved_labels:
                number += 1
            counts[prefix] = number
            placeholders[key] = f"[{prefix}_{counts[prefix]}]"
        pieces.extend((text[previous_end:finding.start], placeholders[key]))
        previous_end = finding.end
    pieces.append(text[previous_end:])
    return "".join(pieces)
