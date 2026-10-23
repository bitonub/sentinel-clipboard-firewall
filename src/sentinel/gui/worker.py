"""One static analysis operation; signals carry results or static diagnostics."""

from dataclasses import asdict, dataclass
import json

from PySide6.QtCore import QThread, Signal

from sentinel.core.command_guard import CommandSyntaxError, check_command
from sentinel.core.sanitize import sanitize
from sentinel.core.scan import scan
from sentinel.limits import InputError, utf8_size


MAX_PRESENTED_FINDINGS = 200


@dataclass(frozen=True)
class Result:
    text: str
    total: int
    shown: int | None  # None means complete sanitized text, not finding rows.


def analyze(text: str, operation: str, shell: str) -> Result:
    utf8_size(text)
    if operation == "sanitize":
        total = len(scan(text))
        return Result(sanitize(text), total, None)
    if operation == "scan":
        findings = scan(text)
    elif operation == "check-command":
        findings = check_command(text, shell=shell)
    else:
        raise ValueError("Operación no admitida.")
    presented = findings[:MAX_PRESENTED_FINDINGS]
    return Result(json.dumps([asdict(f) for f in presented], ensure_ascii=False, indent=2),
                  len(findings), len(presented))


class Worker(QThread):
    # Only run() executes in the worker thread; no slots or GUI work live there.
    completed = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, job: int, text: str, operation: str, shell: str, parent=None):
        super().__init__(parent)
        self.job = job
        self._text = text
        self.operation = operation
        self.shell = shell

    def run(self):
        try:
            result = analyze(self._text, self.operation, self.shell)
        except InputError:
            self.failed.emit(self.job, "Error: entrada inválida o superior a 1 MiB UTF-8.")
        except CommandSyntaxError:
            self.failed.emit(self.job, "Error: no se pudo analizar la sintaxis del comando.")
        except Exception:
            self.failed.emit(self.job, "Error: no se pudo completar la operación.")
        else:
            self.completed.emit(self.job, result)
        finally:
            self._text = ""
