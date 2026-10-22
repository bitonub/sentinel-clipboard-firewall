from sentinel.detectors.private_ipv4 import scan


def sanitize(text: str) -> str:
    pieces = []
    placeholders: dict[str, str] = {}
    previous_end = 0
    for finding in scan(text):
        value = text[finding.start:finding.end]
        if value not in placeholders:
            placeholders[value] = f"[PRIVATE_IP_{len(placeholders) + 1}]"
        pieces.extend((text[previous_end:finding.start], placeholders[value]))
        previous_end = finding.end
    pieces.append(text[previous_end:])
    return "".join(pieces)
