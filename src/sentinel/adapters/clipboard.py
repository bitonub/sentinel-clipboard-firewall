"""Clipboard contracts and explicit, deferred platform selection."""

from dataclasses import dataclass
import sys


class ClipboardError(Exception):
    """Only static, non-sensitive diagnostics may be supplied here."""


@dataclass(frozen=True)
class ClipboardResult:
    changed: bool
    findings: int


def sanitize_clipboard() -> ClipboardResult:
    if sys.platform == "win32":
        from sentinel.adapters.windows import sanitize_clipboard as operation
    elif sys.platform.startswith("linux"):
        from sentinel.adapters.wayland import sanitize_clipboard as operation
    else:
        raise ClipboardError("Portapapeles no compatible con esta plataforma.")
    return operation()
