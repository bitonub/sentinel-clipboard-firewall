"""Explicit Wayland clipboard I/O; the inspection core never starts processes."""

import os
import selectors
import subprocess
import time

from sentinel.core.sanitize import sanitize
from sentinel.core.scan import scan
from sentinel.limits import MAX_INPUT_BYTES
from sentinel.adapters.clipboard import ClipboardError, ClipboardResult


TOOL_TIMEOUT = 5.0
CLEANUP_TIMEOUT = 2.0
PASTE_COMMAND = ("wl-paste", "--no-newline", "--type", "text")
COPY_COMMAND = ("wl-copy", "--type", "text/plain;charset=utf-8", "--sensitive")


def _close_resource(resource) -> bool:
    if resource is None:
        return True
    try:
        resource.close()
        return True
    except Exception:
        return False


def _cleanup_process(process) -> bool:
    """Best effort only: never disclose cleanup errors or wait without a bound."""
    if process is None:
        return True
    ok = True
    deadline = time.monotonic() + CLEANUP_TIMEOUT
    try:
        active = process.poll() is None
    except Exception:
        active = True
        ok = False
    if active:
        try:
            process.kill()
        except Exception:
            ok = False
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                ok = False
            else:
                process.wait(timeout=remaining)
        except Exception:
            ok = False
    # Both Popen instances use bufsize=0: closing stdin cannot flush a
    # buffered payload to an unresponsive consumer.
    for stream in (process.stdin, process.stdout, process.stderr):
        if not _close_resource(stream):
            ok = False
    return ok


def _read_clipboard() -> bytes:
    process = None
    selector = None
    error = None
    try:
        deadline = time.monotonic() + TOOL_TIMEOUT
        process = subprocess.Popen(
            PASTE_COMMAND, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, shell=False, bufsize=0,
        )
        data = bytearray()
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise ClipboardError("Tiempo de lectura del portapapeles agotado.")
            chunk = os.read(process.stdout.fileno(), min(65536, MAX_INPUT_BYTES + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_INPUT_BYTES:
                raise ClipboardError("El texto del portapapeles supera 1 MiB.")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ClipboardError("Tiempo de lectura del portapapeles agotado.")
        if process.wait(timeout=remaining) != 0:
            raise ClipboardError("No se pudo leer el portapapeles.")
        content = bytes(data)
    except FileNotFoundError:
        error = ClipboardError("No se encontró wl-paste.")
    except subprocess.TimeoutExpired:
        error = ClipboardError("Tiempo de lectura del portapapeles agotado.")
    except ClipboardError as caught:
        error = caught
    except Exception:
        error = ClipboardError("No se pudo leer el portapapeles.")
    finally:
        selector_ok = _close_resource(selector)
        process_ok = _cleanup_process(process)
    if error is not None:
        raise error from None
    if not selector_ok or not process_ok:
        raise ClipboardError("No se pudo finalizar la lectura del portapapeles.")
    return content


def _write_clipboard(payload: bytes) -> None:
    process = None
    error = None
    try:
        process = subprocess.Popen(
            COPY_COMMAND, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, shell=False, bufsize=0,
        )
        process.communicate(input=payload, timeout=TOOL_TIMEOUT)
        if process.returncode != 0:
            raise ClipboardError("No se pudo escribir el portapapeles.")
    except FileNotFoundError:
        error = ClipboardError("No se encontró wl-copy.")
    except subprocess.TimeoutExpired:
        error = ClipboardError("Tiempo de escritura del portapapeles agotado.")
    except ClipboardError as caught:
        error = caught
    except Exception:
        error = ClipboardError("No se pudo escribir el portapapeles.")
    finally:
        cleanup_ok = _cleanup_process(process)
    if error is not None:
        raise error from None
    if not cleanup_ok:
        raise ClipboardError("No se pudo finalizar la escritura del portapapeles.")


def sanitize_clipboard() -> ClipboardResult:
    raw = _read_clipboard()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ClipboardError("El portapapeles no contiene UTF-8 válido.") from None
    try:
        count = len(scan(text))
        result = sanitize(text)
        payload = result.encode("utf-8")
    except Exception:
        raise ClipboardError("No se pudo sanitizar el portapapeles.") from None
    if result == text:
        return ClipboardResult(False, count)
    _write_clipboard(payload)
    return ClipboardResult(True, count)
