"""Explicit Win32 text clipboard operation with an injectable native API.

No DLL is loaded on import. Native calls are synchronous: the retry deadline
only bounds contention at OpenClipboard, not delayed rendering by Windows.
"""

import codecs
from contextlib import contextmanager
import time

from sentinel.adapters.clipboard import ClipboardError, ClipboardResult
from sentinel.core.sanitize import sanitize
from sentinel.core.scan import scan
from sentinel.limits import MAX_INPUT_BYTES, utf8_size


CF_UNICODETEXT = 13
GMEM_FLAGS = 0x0042  # GMEM_MOVEABLE | GMEM_ZEROINIT
READ_BLOCK_BYTES = 8192
MAX_UTF16_BYTES = 2 * (MAX_INPUT_BYTES + 1)  # Includes the UTF-16 NUL.
OPEN_TIMEOUT = 5.0
RETRY_INTERVAL = 0.025

READ_ERROR = "No se pudo leer el portapapeles de Windows."
INVALID_TEXT = "El portapapeles no contiene texto Unicode válido y terminado."
SIZE_ERROR = "El texto del portapapeles supera 1 MiB UTF-8."
CONFLICT = "El portapapeles cambió; vuelve a intentarlo."
CLEANUP_ERROR = "No se pudieron liberar los recursos del portapapeles."
WRITE_ERROR = "No se pudo completar la escritura; el portapapeles puede haber cambiado."
GENERIC_ERROR = "No se pudo completar la operación de portapapeles de Windows."


class _Failure(Exception):
    """Internal static diagnostics, converted at the public boundary."""


class Win32API:
    """Typed Win32 binding; construction is deferred until an explicit request."""

    def __init__(self, *, loader=None):
        import ctypes

        self._ctypes = ctypes
        if loader is None:
            loader = ctypes.WinDLL
        options = dict(use_last_error=True, winmode=0x00000800)  # SEARCH_SYSTEM32
        user = loader("user32.dll", **options)
        kernel = loader("kernel32.dll", **options)
        pointer = ctypes.c_void_p
        uint = ctypes.c_uint32
        boolean = ctypes.c_int32
        integer = ctypes.c_int32
        # Fixed-width Win32 types; HANDLE/HWND and SIZE_T follow pointer width.
        bindings = (
            (user, "OpenClipboard", [pointer], boolean),
            (user, "CloseClipboard", [], boolean),
            (user, "IsClipboardFormatAvailable", [uint], boolean),
            (user, "GetClipboardData", [uint], pointer),
            (user, "GetClipboardSequenceNumber", [], uint),
            (user, "EmptyClipboard", [], boolean),
            (user, "SetClipboardData", [uint, pointer], pointer),
            (user, "CreateWindowExW", [uint, ctypes.c_wchar_p, ctypes.c_wchar_p, uint,
                                       integer, integer, integer, integer,
                                       pointer, pointer, pointer, pointer], pointer),
            (user, "DestroyWindow", [pointer], boolean),
            (kernel, "GlobalSize", [pointer], ctypes.c_size_t),
            (kernel, "GlobalLock", [pointer], pointer),
            (kernel, "GlobalUnlock", [pointer], boolean),
            (kernel, "GlobalAlloc", [uint, ctypes.c_size_t], pointer),
            (kernel, "GlobalFree", [pointer], pointer),
        )
        for library, name, arguments, result in bindings:
            function = getattr(library, name)
            function.argtypes, function.restype = arguments, result
            setattr(self, name, function)

    def set_last_error(self, value):
        self._ctypes.set_last_error(value)

    def get_last_error(self):
        return self._ctypes.get_last_error()

    def read_memory(self, pointer, offset, size):
        return self._ctypes.string_at(pointer + offset, size)

    def write_memory(self, pointer, payload):
        self._ctypes.memmove(pointer, payload, len(payload))


def _attempt(operation):
    try:
        return bool(operation())
    except Exception:
        return False


@contextmanager
def _opened(api, hwnd, clock, sleep):
    deadline = clock() + OPEN_TIMEOUT
    while not api.OpenClipboard(hwnd):
        remaining = deadline - clock()
        if remaining <= 0:
            raise _Failure("Tiempo de apertura del portapapeles agotado.")
        sleep(min(RETRY_INTERVAL, remaining))
    try:
        yield
    except BaseException:
        _attempt(api.CloseClipboard)
        raise
    else:
        if not _attempt(api.CloseClipboard):
            raise _Failure(CLEANUP_ERROR)


def _unlock(api, handle):
    # Zero means either a successful final unlock or an error. Clear stale
    # last-error state before the call, and read it only for a zero result.
    api.set_last_error(0)
    return bool(api.GlobalUnlock(handle)) or api.get_last_error() == 0


@contextmanager
def _locked(api, handle):
    pointer = api.GlobalLock(handle)
    if not pointer:
        raise _Failure("No se pudo bloquear la memoria del portapapeles.")
    try:
        yield pointer
    except BaseException:
        _attempt(lambda: _unlock(api, handle))
        raise
    else:
        if not _attempt(lambda: _unlock(api, handle)):
            raise _Failure(CLEANUP_ERROR)


def _read_text(api):
    if not api.IsClipboardFormatAvailable(CF_UNICODETEXT):
        raise _Failure("El portapapeles no contiene texto Unicode disponible.")
    handle = api.GetClipboardData(CF_UNICODETEXT)
    if not handle:
        raise _Failure(READ_ERROR)
    size = api.GlobalSize(handle)
    if size < 2:
        raise _Failure(INVALID_TEXT)
    # GlobalSize may include padding, even an odd trailing byte. Only inspect
    # complete UTF-16 units, and never reject a short string just for padding.
    limit = min(size - size % 2, MAX_UTF16_BYTES)
    decoder = codecs.getincrementaldecoder("utf-16-le")("strict")
    parts, total = [], 0
    with _locked(api, handle) as pointer:
        for offset in range(0, limit, READ_BLOCK_BYTES):
            count = min(READ_BLOCK_BYTES, limit - offset)
            data = api.read_memory(pointer, offset, count)
            if len(data) != count:
                raise _Failure(READ_ERROR)
            end = next((i for i in range(0, len(data), 2) if data[i:i + 2] == b"\0\0"), None)
            try:
                text = decoder.decode(data if end is None else data[:end], final=end is not None)
            except UnicodeDecodeError:
                raise _Failure(INVALID_TEXT) from None
            total += len(text.encode("utf-8"))
            if total > MAX_INPUT_BYTES:
                raise _Failure(SIZE_ERROR)
            parts.append(text)
            if end is not None:
                return "".join(parts)
    raise _Failure(SIZE_ERROR if size > MAX_UTF16_BYTES else INVALID_TEXT)


def _sequence(api):
    value = api.GetClipboardSequenceNumber()
    if not value:
        raise _Failure("No se pudo comprobar la secuencia del portapapeles.")
    return value


def sanitize_clipboard(api=None, *, clock=time.monotonic, sleep=time.sleep) -> ClipboardResult:
    """Sanitize once; all API/memory operations can be simulated on any host."""
    owned = hwnd = None
    release_allowed = True
    mutation_started = False
    error = None
    result = None
    try:
        if api is None:
            api = Win32API()
        with _opened(api, None, clock, sleep):
            text = _read_text(api)
            sequence = _sequence(api)  # After any delayed rendering.
        try:
            utf8_size(text)
            count = len(scan(text))
            sanitized = sanitize(text)
            payload = sanitized.encode("utf-16-le") + b"\0\0"
        except Exception:
            raise _Failure("No se pudo sanitizar el portapapeles.") from None
        result = ClipboardResult(sanitized != text, count)
        if result.changed:
            # Fully prepare and unlock the output before any destructive call.
            owned = api.GlobalAlloc(GMEM_FLAGS, len(payload))
            if not owned:
                raise _Failure("No se pudo reservar memoria para el portapapeles.")
            with _locked(api, owned) as pointer:
                api.write_memory(pointer, payload)
            hwnd = api.CreateWindowExW(0, "STATIC", "SENTINEL", 0, 0, 0, 0, 0,
                                       None, None, None, None)
            if not hwnd:
                raise _Failure("No se pudo crear la ventana del portapapeles.")
            with _opened(api, hwnd, clock, sleep):
                if _sequence(api) != sequence:
                    raise _Failure(CONFLICT)
                current = _read_text(api)
                if current != text or _sequence(api) != sequence:
                    raise _Failure(CONFLICT)
                mutation_started = True  # EmptyClipboard itself may fail.
                if not api.EmptyClipboard():
                    raise _Failure(WRITE_ERROR)
                # Stop freeing BEFORE crossing the native boundary: cancellation
                # can hide whether Windows acquired the block. An ambiguous
                # outcome may leak it, but must never free system-owned memory.
                release_allowed = False
                published = api.SetClipboardData(CF_UNICODETEXT, owned)
                if not published:
                    release_allowed = True  # Confirmed failure: still ours.
                    raise _Failure(WRITE_ERROR)
    except _Failure as caught:
        error = ClipboardError(WRITE_ERROR if mutation_started else str(caught))
    except Exception:
        error = ClipboardError(WRITE_ERROR if mutation_started else GENERIC_ERROR)
    finally:
        freed = destroyed = True
        if owned and release_allowed:
            freed = _attempt(lambda: api.GlobalFree(owned) is None)
        if hwnd:
            destroyed = _attempt(lambda: api.DestroyWindow(hwnd))
        if error is None and not (freed and destroyed):
            error = ClipboardError(WRITE_ERROR if mutation_started else CLEANUP_ERROR)
    if error is not None:
        raise error from None
    return result
