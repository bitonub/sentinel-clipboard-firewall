from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    rule_id: str
    category: str
    start: int
    end: int
    severity: str
    explanation: str
