"""Win32 protocol tests: only synthetic memory, never the host clipboard."""

from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
import ctypes
import inspect
import io
import sys
import unittest
from unittest.mock import MagicMock, patch

from sentinel import cli
from sentinel.adapters import windows
from sentinel.adapters.clipboard import ClipboardError, ClipboardResult
from sentinel.core.sanitize import sanitize


MARKER = "SYNTHETIC_SECRET_MARKER"
DEFAULT = object()


class FakeAPI:
    """Model native ownership, lock counts, API errors and memory boundaries."""

    def __init__(self, text="α password=" + MARKER + " host=10.0.0.1\r\n😀"):
        self.borrowed = 2**40
        self.memory = {self.borrowed: bytearray(text.encode("utf-16-le") + b"\0\0")}
        self.calls = []
        self.counts = Counter()
        self.hooks = {}
        self.locks = Counter()
        self.error = 999  # A previous unrelated Win32 failure.
        self.sequence = 41
        self.opened = False
        self.hwnd = 2**40 + 100
        self.allocated = None
        self.transferred = None
        self.free_attempts = []
        self.forbidden_frees = []
        self.now = 0

    def event(self, name, *args):
        self.calls.append((name, *args))
        self.counts[name] += 1
        hook = self.hooks.get((name, self.counts[name]))
        if callable(hook):
            return hook()
        if isinstance(hook, BaseException):
            raise hook
        return DEFAULT if hook is None else hook

    def clock(self):
        return self.now

    def sleep(self, seconds):
        assert 0 < seconds <= windows.RETRY_INTERVAL
        self.now += seconds

    def OpenClipboard(self, hwnd):
        value = self.event("OpenClipboard", hwnd)
        if value is not DEFAULT:
            return value
        assert not self.opened
        self.opened = True
        return 1

    def CloseClipboard(self):
        value = self.event("CloseClipboard")
        if value is not DEFAULT:
            return value
        assert self.opened
        self.opened = False
        return 1

    def IsClipboardFormatAvailable(self, format):
        assert self.opened and format == windows.CF_UNICODETEXT
        value = self.event("IsClipboardFormatAvailable", format)
        return 1 if value is DEFAULT else value

    def GetClipboardData(self, format):
        assert self.opened and format == windows.CF_UNICODETEXT
        value = self.event("GetClipboardData", format)
        return self.borrowed if value is DEFAULT else value

    def GetClipboardSequenceNumber(self):
        assert self.opened
        value = self.event("GetClipboardSequenceNumber")
        return self.sequence if value is DEFAULT else value

    def GlobalSize(self, handle):
        value = self.event("GlobalSize", handle)
        return len(self.memory[handle]) if value is DEFAULT else value

    def GlobalLock(self, handle):
        value = self.event("GlobalLock", handle)
        if value is not DEFAULT:
            return value
        self.locks[handle] += 1
        return handle

    def set_last_error(self, value):
        self.event("set_last_error", value)
        self.error = value

    def get_last_error(self):
        self.event("get_last_error")
        return self.error

    def GlobalUnlock(self, handle):
        value = self.event("GlobalUnlock", handle)
        if value is not DEFAULT:
            return value
        assert self.locks[handle] > 0
        self.locks[handle] -= 1
        return int(self.locks[handle] > 0)

    def read_memory(self, pointer, offset, size):
        assert self.locks[pointer] > 0 and self.opened
        assert size > 0 and offset + size <= len(self.memory[pointer])
        value = self.event("read_memory", pointer, offset, size)
        return bytes(self.memory[pointer][offset:offset + size]) if value is DEFAULT else value

    def GlobalAlloc(self, flags, size):
        assert not self.opened and flags == windows.GMEM_FLAGS
        value = self.event("GlobalAlloc", flags, size)
        if value is not DEFAULT:
            return value
        self.allocated = self.borrowed + 1
        self.memory[self.allocated] = bytearray(size)
        return self.allocated

    def write_memory(self, pointer, payload):
        assert not self.opened and self.locks[pointer] > 0
        assert len(payload) == len(self.memory[pointer])
        self.event("write_memory", pointer, len(payload))
        self.memory[pointer][:] = payload

    def CreateWindowExW(self, *args):
        assert not self.opened
        assert args == (0, "STATIC", "SENTINEL", 0, 0, 0, 0, 0, None, None, None, None)
        value = self.event("CreateWindowExW", *args)
        return self.hwnd if value is DEFAULT else value

    def EmptyClipboard(self):
        assert self.opened
        assert self.allocated and self.locks[self.allocated] == 0
        value = self.event("EmptyClipboard")
        if value is not DEFAULT:
            return value
        self.memory.pop(self.borrowed)
        self.sequence += 1
        return 1

    def SetClipboardData(self, format, handle):
        assert self.opened and format == windows.CF_UNICODETEXT
        assert self.locks[handle] == 0 and handle == self.allocated
        value = self.event("SetClipboardData", format, handle)
        if value is not DEFAULT:
            return value
        self.transferred = handle
        return handle

    def GlobalFree(self, handle):
        # Record BEFORE assertions/hooks: production cleanup contains Exceptions.
        self.free_attempts.append(handle)
        forbidden = handle in (self.borrowed, self.transferred)
        if forbidden:
            self.forbidden_frees.append(handle)
        value = self.event("GlobalFree", handle)
        assert not forbidden
        if value is not DEFAULT:
            return value
        self.memory.pop(handle)
        return None

    def DestroyWindow(self, hwnd):
        assert hwnd == self.hwnd
        value = self.event("DestroyWindow", hwnd)
        return 1 if value is DEFAULT else value


class WindowsClipboardTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeAPI()
        # A missing injection must fail the test, even on Windows CI.
        self.factory = self.enterContext(patch.object(windows, "Win32API", side_effect=AssertionError("Real API forbidden")))

    def operation(self):
        try:
            return windows.sanitize_clipboard(self.api, clock=self.api.clock, sleep=self.api.sleep)
        finally:
            # Outside the adapter, so its protected cleanup cannot swallow this.
            self.assert_ownership(self.api)

    def assert_ownership(self, api):
        self.assertEqual(api.forbidden_frees, [])
        self.assertNotIn(api.borrowed, api.free_attempts)
        if api.transferred is not None:
            self.assertNotIn(api.transferred, api.free_attempts)

    def invoke(self):
        out, err = io.StringIO(), io.StringIO()
        with (patch("sentinel.cli.sanitize_clipboard", self.operation),
              patch("sys.argv", ["sentinel", "clipboard", "sanitize"]),
              redirect_stdout(out), redirect_stderr(err)):
            code = cli.main()
        self.assertNotIn(MARKER, out.getvalue() + err.getvalue())
        self.assertNotIn("Traceback", out.getvalue() + err.getvalue())
        return code, out.getvalue(), err.getvalue()

    def assert_prewrite_failure(self):
        code, out, error = self.invoke()
        self.assertEqual((code, out), (2, ""))
        self.assertTrue(error.startswith("Error:"))
        self.assertEqual(self.api.counts["EmptyClipboard"], 0)
        self.assertEqual(self.api.counts["SetClipboardData"], 0)
        return error

    def test_success_preserves_unicode_and_transfers_prepared_memory(self):
        text = bytes(self.api.memory[self.api.borrowed][:-2]).decode("utf-16-le")
        self.assertEqual(self.invoke(), (0, "Portapapeles actualizado; hallazgos: 2.\n", ""))
        self.assertEqual(bytes(self.api.memory[self.api.transferred]), sanitize(text).encode("utf-16-le") + b"\0\0")
        self.assertFalse(self.api.opened)
        self.assertTrue(all(value == 0 for value in self.api.locks.values()))
        self.assertEqual(self.api.counts["GlobalFree"], 0)
        self.assertEqual(self.api.counts["CloseClipboard"], 2)
        self.assertEqual(self.api.counts["DestroyWindow"], 1)
        names = [call[0] for call in self.api.calls]
        self.assertLess(names.index("write_memory"), names.index("EmptyClipboard"))
        self.assertEqual([call[1] for call in self.api.calls if call[0] == "OpenClipboard"], [None, self.api.hwnd])

    def test_cli_selects_windows_and_uses_only_the_injected_api(self):
        out, err = io.StringIO(), io.StringIO()
        with (patch("sentinel.adapters.clipboard.sys.platform", "win32"),
              patch.object(windows, "Win32API", return_value=self.api),
              patch("sys.argv", ["sentinel", "clipboard", "sanitize"]),
              redirect_stdout(out), redirect_stderr(err)):
            self.assertEqual(cli.main(), 0)
        self.assertEqual(out.getvalue(), "Portapapeles actualizado; hallazgos: 2.\n")
        self.assertEqual(err.getvalue(), "")
        self.assertEqual(self.api.counts["SetClipboardData"], 1)
        self.assert_ownership(self.api)

    def test_no_changes_and_empty_text_do_not_allocate_or_write(self):
        for text in ("", "synthetic public text 😀\r\n", "password=[PASSWORD_1]"):
            with self.subTest(text=text):
                self.api = FakeAPI(text)
                self.assertEqual(self.operation(), ClipboardResult(False, 0))
                for name in ("GlobalAlloc", "write_memory", "CreateWindowExW", "EmptyClipboard", "SetClipboardData"):
                    self.assertEqual(self.api.counts[name], 0)

    def test_exact_utf8_byte_limit_and_one_byte_excess(self):
        for char in ("x", "é", "😀"):
            with self.subTest(char=char):
                text = char * (windows.MAX_INPUT_BYTES // len(char.encode("utf-8")))
                self.api = FakeAPI(text)
                self.assertFalse(self.operation().changed)
                self.api = FakeAPI(text + "x")
                self.assertIn("1 MiB", self.assert_prewrite_failure())

    def test_huge_allocation_is_read_with_a_fixed_bound(self):
        self.api.memory[self.api.borrowed] = bytearray(b"x\0" * (windows.MAX_INPUT_BYTES * 2))
        self.assert_prewrite_failure()
        reads = [call for call in self.api.calls if call[0] == "read_memory"]
        self.assertLessEqual(sum(call[3] for call in reads), windows.MAX_UTF16_BYTES)
        self.assertLessEqual(max(call[3] for call in reads), windows.READ_BLOCK_BYTES)

    def test_padding_is_not_text_even_with_an_odd_allocation_size(self):
        self.api = FakeAPI("public")
        self.api.memory[self.api.borrowed].extend(b"\xff" * (windows.MAX_UTF16_BYTES + 1))
        self.assertFalse(self.operation().changed)
        self.assertEqual(self.api.counts["read_memory"], 1)

    def test_surrogate_pair_split_between_blocks_is_decoded_incrementally(self):
        prefix = "x" * (windows.READ_BLOCK_BYTES // 2 - 1)
        self.api = FakeAPI(prefix + "😀 password=" + MARKER)
        self.assertTrue(self.operation().changed)
        output = bytes(self.api.memory[self.api.transferred][:-2]).decode("utf-16-le")
        self.assertEqual(output, prefix + "😀 password=[PASSWORD_1]")

    def test_invalid_surrogates_and_missing_terminators_are_safe(self):
        prefix = b"x\0" * (windows.READ_BLOCK_BYTES // 2 - 1)
        for data in (b"\x00\xd8\0\0", b"\x00\xdc\0\0", prefix + b"\x00\xd8x\0\0\0",
                     b"x\0", b"x", b"", prefix + b"\x00\xd8"):
            with self.subTest(length=len(data)):
                self.api = FakeAPI()
                self.api.memory[self.api.borrowed] = bytearray(data)
                self.assert_prewrite_failure()

    def test_sanitized_output_may_exceed_input_budget_and_is_idempotent(self):
        text = "password=x\n" * (windows.MAX_INPUT_BYTES // len("password=x\n"))
        self.api = FakeAPI(text)
        self.assertTrue(self.operation().changed)
        output = bytes(self.api.memory[self.api.transferred][:-2]).decode("utf-16-le")
        self.assertGreater(len(output.encode("utf-8")), windows.MAX_INPUT_BYTES)
        self.assertEqual(output, sanitize(text))
        # Reapplying the motor is idempotent. The adapter's input budget still
        # applies to a second invocation, including expanded sanitized text.
        self.assertEqual(sanitize(output), output)

    def test_repeated_values_and_second_operation_do_not_share_maps(self):
        for text in ("password=" + MARKER + " pwd=" + MARKER, "password=SyntheticOther42"):
            self.api = FakeAPI(text)
            self.assertTrue(self.operation().changed)
            output = bytes(self.api.memory[self.api.transferred][:-2]).decode("utf-16-le")
            self.assertEqual(output, sanitize(text))
            self.api = FakeAPI(output)
            self.assertFalse(self.operation().changed)
            self.assertEqual(self.api.counts["SetClipboardData"], 0)

    def test_zero_unlock_clears_stale_error_and_succeeds(self):
        self.assertTrue(self.operation().changed)
        self.assertEqual(self.api.counts["set_last_error"], 3)
        self.assertEqual(self.api.counts["get_last_error"], 3)

    def test_zero_unlock_with_a_new_error_prevents_writing(self):
        for index in (1, 2, 3):
            with self.subTest(unlock=index):
                self.api = FakeAPI()

                def fail():
                    self.assertEqual(self.api.error, 0)
                    self.api.error = 5
                    return 0

                self.api.hooks[("GlobalUnlock", index)] = fail
                self.assert_prewrite_failure()
                self.assertFalse(self.api.opened)
                self.assertEqual(self.api.counts["GlobalFree"], int(index > 1))

    def test_nonzero_unlock_does_not_release_someone_elses_lock(self):
        self.api.locks[self.api.borrowed] = 1
        self.assertTrue(self.operation().changed)
        self.assertEqual(self.api.locks[self.api.borrowed], 1)

    def test_concurrent_sequence_change_never_empties_or_sets(self):
        for index in (2, 3):
            with self.subTest(sequence_call=index):
                self.api = FakeAPI()
                self.api.hooks[("GetClipboardSequenceNumber", index)] = 42
                self.assertIn("cambió", self.assert_prewrite_failure())
                self.assertEqual(self.api.counts["GlobalFree"], 1)
                self.assertEqual(self.api.counts["DestroyWindow"], 1)

    def test_same_sequence_with_changed_text_is_also_a_conflict(self):
        def change():
            self.api.memory[self.api.borrowed] = bytearray("new synthetic text\0".encode("utf-16-le"))
            return DEFAULT

        self.api.hooks[("OpenClipboard", 2)] = change
        self.assertIn("cambió", self.assert_prewrite_failure())

    def test_unavailable_sequence_prevents_writing(self):
        self.api.hooks[("GetClipboardSequenceNumber", 1)] = 0
        self.assert_prewrite_failure()

    def test_read_and_preparation_api_failures_are_safe(self):
        for name, index, value in (("IsClipboardFormatAvailable", 1, 0), ("GetClipboardData", 1, 0),
                                   ("GlobalSize", 1, 0), ("GlobalLock", 1, 0), ("GlobalAlloc", 1, 0),
                                   ("CreateWindowExW", 1, 0), ("read_memory", 1, b""),
                                   ("write_memory", 1, OSError(MARKER)), ("GlobalLock", 2, 0),
                                   ("GetClipboardData", 2, 0)):
            with self.subTest(api=name, call=index):
                self.api = FakeAPI()
                self.api.hooks[(name, index)] = value
                self.assert_prewrite_failure()
                self.assertFalse(self.api.opened)
                if self.api.allocated:
                    self.assertEqual(self.api.counts["GlobalFree"], 1)

    def test_analysis_errors_prevent_any_write(self):
        for name in ("scan", "sanitize"):
            with self.subTest(operation=name), patch.object(windows, name, side_effect=RuntimeError(MARKER)):
                self.api = FakeAPI()
                self.assertIn("sanitizar", self.assert_prewrite_failure())
                self.assertEqual(self.api.counts["GlobalAlloc"], 0)

    def test_retry_deadline_and_eventual_success(self):
        self.api.hooks[("OpenClipboard", 1)] = 0
        self.assertTrue(self.operation().changed)
        self.assertGreater(self.api.now, 0)
        self.api = FakeAPI()
        for i in range(1, 1000):
            self.api.hooks[("OpenClipboard", i)] = 0
        self.assertIn("agotado", self.assert_prewrite_failure())
        self.assertLessEqual(self.api.now, windows.OPEN_TIMEOUT)
        self.assertEqual(self.api.counts["CloseClipboard"], 0)

    def test_reopen_timeout_releases_prepared_memory_and_window(self):
        for index in range(2, 1000):
            self.api.hooks[("OpenClipboard", index)] = 0
        self.assertIn("agotado", self.assert_prewrite_failure())
        self.assertEqual(self.api.counts["GlobalFree"], 1)
        self.assertEqual(self.api.counts["DestroyWindow"], 1)
        self.assertEqual(self.api.counts["CloseClipboard"], 1)
        self.assertFalse(self.api.opened)

    def test_write_failures_free_only_untransferred_memory(self):
        for name in ("EmptyClipboard", "SetClipboardData"):
            with self.subTest(api=name):
                self.api = FakeAPI()
                self.api.hooks[(name, 1)] = 0
                code, out, error = self.invoke()
                self.assertEqual((code, out), (2, ""))
                self.assertIn("puede haber cambiado", error)
                self.assertEqual(self.api.counts["GlobalFree"], 1)
                self.assertEqual(self.api.counts["DestroyWindow"], 1)
                self.assertFalse(self.api.opened)

    def test_cleanup_after_success_never_frees_transferred_memory(self):
        for name, index, failure in (("CloseClipboard", 2, 0), ("CloseClipboard", 2, OSError(MARKER)),
                                     ("DestroyWindow", 1, 0), ("DestroyWindow", 1, OSError(MARKER))):
            with self.subTest(api=name, failure=type(failure).__name__):
                self.api = FakeAPI()
                self.api.hooks[(name, index)] = failure
                code, out, error = self.invoke()
                self.assertEqual((code, out), (2, ""))
                self.assertIn("puede haber cambiado", error)
                self.assertIsNotNone(self.api.transferred)
                self.assertIn(self.api.transferred, self.api.memory)
                self.assertEqual(self.api.counts["GlobalFree"], 0)
                self.assertEqual(self.api.counts["DestroyWindow"], 1)

    def test_prohibited_free_remains_observable_when_cleanup_contains_assertion(self):
        api = FakeAPI()
        api.transferred = api.allocated = api.borrowed + 1
        for handle in (api.borrowed, api.transferred):
            with self.subTest(handle=handle):
                self.assertFalse(windows._attempt(lambda: api.GlobalFree(handle)))
                self.assertEqual(api.free_attempts[-1], handle)
                self.assertEqual(api.forbidden_frees[-1], handle)
                with self.assertRaises(AssertionError):
                    self.assert_ownership(api)
        self.assertEqual(api.counts["GlobalFree"], 2)

    def test_cancellation_before_transfer_frees_prepared_memory(self):
        interruption = KeyboardInterrupt()
        self.api.hooks[("EmptyClipboard", 1)] = interruption
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.operation()
        self.assertIs(caught.exception, interruption)
        self.assertEqual(self.api.free_attempts, [self.api.allocated])
        self.assertEqual(self.api.counts["SetClipboardData"], 0)
        self.assertFalse(self.api.opened)
        self.assertEqual(self.api.counts["DestroyWindow"], 1)

    def test_interrupted_transfer_keeps_ambiguous_memory_and_propagates_cancellation(self):
        for acquired in (False, True):
            with self.subTest(acquired=acquired):
                self.api = FakeAPI()
                interruption = KeyboardInterrupt()

                def interrupted_transfer():
                    if acquired:
                        self.api.transferred = self.api.allocated
                    raise interruption

                self.api.hooks[("SetClipboardData", 1)] = interrupted_transfer
                with self.assertRaises(KeyboardInterrupt) as caught:
                    self.operation()
                self.assertIs(caught.exception, interruption)
                self.assertEqual(self.api.free_attempts, [])
                self.assertIn(self.api.allocated, self.api.memory)
                self.assertFalse(self.api.opened)
                self.assertEqual(self.api.counts["DestroyWindow"], 1)

    def test_interruption_after_native_return_before_confirmation_keeps_memory(self):
        source, first_line = inspect.getsourcelines(windows.sanitize_clipboard)
        boundary = first_line + next(i for i, line in enumerate(source) if "if not published:" in line)
        for succeeded in (False, True):
            with self.subTest(succeeded=succeeded):
                self.api = FakeAPI()
                if not succeeded:
                    self.api.hooks[("SetClipboardData", 1)] = 0
                interruption = KeyboardInterrupt()

                def interrupt(frame, event, arg):
                    if (frame.f_code is windows.sanitize_clipboard.__code__
                            and event == "line" and frame.f_lineno == boundary):
                        raise interruption
                    return interrupt

                previous = sys.gettrace()
                try:
                    sys.settrace(interrupt)
                    with self.assertRaises(KeyboardInterrupt) as caught:
                        self.operation()
                finally:
                    sys.settrace(previous)
                self.assertIs(caught.exception, interruption)
                self.assertEqual(self.api.counts["SetClipboardData"], 1)
                self.assertEqual(self.api.transferred, self.api.allocated if succeeded else None)
                self.assertEqual(self.api.free_attempts, [])
                self.assertIn(self.api.allocated, self.api.memory)
                self.assertFalse(self.api.opened)
                self.assertEqual(self.api.counts["DestroyWindow"], 1)

    def test_unconfirmed_transfer_exception_uses_safe_error_without_freeing(self):
        self.api.hooks[("SetClipboardData", 1)] = OSError(MARKER)
        code, out, error = self.invoke()
        self.assertEqual((code, out), (2, ""))
        self.assertIn("puede haber cambiado", error)
        self.assertEqual(self.api.free_attempts, [])
        self.assertIn(self.api.allocated, self.api.memory)
        self.assertFalse(self.api.opened)
        self.assertEqual(self.api.counts["DestroyWindow"], 1)

    def test_cancellation_during_close_preserves_confirmed_transfer_outcome(self):
        for succeeded in (False, True):
            with self.subTest(succeeded=succeeded):
                self.api = FakeAPI()
                if not succeeded:
                    self.api.hooks[("SetClipboardData", 1)] = 0
                interruption = KeyboardInterrupt()
                self.api.hooks[("CloseClipboard", 2)] = interruption
                with self.assertRaises(KeyboardInterrupt) as caught:
                    self.operation()
                self.assertIs(caught.exception, interruption)
                expected = [] if succeeded else [self.api.allocated]
                self.assertEqual(self.api.free_attempts, expected)
                self.assertEqual(self.api.allocated in self.api.memory, succeeded)
                self.assertEqual(self.api.counts["DestroyWindow"], 1)

    def test_cleanup_errors_do_not_hide_primary_read_error(self):
        self.api.memory[self.api.borrowed] = bytearray(b"\x00\xd8\0\0")
        self.api.hooks[("GlobalUnlock", 1)] = OSError(MARKER)
        self.api.hooks[("CloseClipboard", 1)] = OSError(MARKER)
        self.assertIn(windows.INVALID_TEXT, self.assert_prewrite_failure())
        self.assertEqual(self.api.counts["GlobalUnlock"], 1)
        self.assertEqual(self.api.counts["CloseClipboard"], 1)

    def test_failed_free_and_destroy_do_not_hide_a_conflict(self):
        self.api.hooks[("GetClipboardSequenceNumber", 2)] = 42
        self.api.hooks[("GlobalFree", 1)] = OSError(MARKER)
        self.api.hooks[("DestroyWindow", 1)] = OSError(MARKER)
        self.assertIn(windows.CONFLICT, self.assert_prewrite_failure())
        self.assertEqual(self.api.counts["GlobalFree"], 1)
        self.assertEqual(self.api.counts["DestroyWindow"], 1)

    def test_read_close_failure_prevents_preparation(self):
        self.api.hooks[("CloseClipboard", 1)] = 0
        self.assert_prewrite_failure()
        self.assertEqual(self.api.counts["GlobalAlloc"], 0)

    def test_native_factory_failure_is_static(self):
        with patch.object(windows, "Win32API", side_effect=OSError(MARKER)):
            with self.assertRaises(ClipboardError) as caught:
                windows.sanitize_clipboard()
        self.assertEqual(str(caught.exception), windows.GENERIC_ERROR)


class Win32BindingTests(unittest.TestCase):
    def test_fixed_system_dlls_and_pointer_sized_signatures_without_loading_them(self):
        libraries = {}

        def loader(name, **options):
            self.assertEqual(options, dict(use_last_error=True, winmode=0x800))
            library = MagicMock()
            libraries[name] = library
            return library

        api = windows.Win32API(loader=loader)
        self.assertEqual(set(libraries), {"user32.dll", "kernel32.dll"})
        pointer, uint, boolean = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int32
        signatures = {
            "user32.dll": {
                "OpenClipboard": ([pointer], boolean),
                "CloseClipboard": ([], boolean),
                "IsClipboardFormatAvailable": ([uint], boolean),
                "GetClipboardData": ([uint], pointer),
                "GetClipboardSequenceNumber": ([], uint),
                "EmptyClipboard": ([], boolean),
                "SetClipboardData": ([uint, pointer], pointer),
                "CreateWindowExW": ([uint, ctypes.c_wchar_p, ctypes.c_wchar_p, uint,
                                     boolean, boolean, boolean, boolean,
                                     pointer, pointer, pointer, pointer], pointer),
                "DestroyWindow": ([pointer], boolean),
            },
            "kernel32.dll": {
                "GlobalSize": ([pointer], ctypes.c_size_t),
                "GlobalLock": ([pointer], pointer),
                "GlobalUnlock": ([pointer], boolean),
                "GlobalAlloc": ([uint, ctypes.c_size_t], pointer),
                "GlobalFree": ([pointer], pointer),
            },
        }
        for dll, functions in signatures.items():
            self.assertEqual(set(libraries[dll]._mock_children), set(functions))
            for name, (arguments, result) in functions.items():
                with self.subTest(dll=dll, function=name):
                    function = getattr(api, name)
                    self.assertIs(function, getattr(libraries[dll], name))
                    self.assertEqual(function.argtypes, arguments)
                    self.assertIs(function.restype, result)
        for library in libraries.values():
            for function in library._mock_children.values():
                function.assert_not_called()
        # Local synthetic memory also exercises the binding's pointer helpers.
        buffer = ctypes.create_string_buffer(b"synthetic", 16)
        address = ctypes.addressof(buffer)
        self.assertEqual(api.read_memory(address, 2, 4), b"nthe")
        api.write_memory(address, b"test")
        self.assertEqual(buffer.raw[:4], b"test")

    def make_native_boundary(self):
        self.assertGreaterEqual(ctypes.sizeof(ctypes.c_void_p), 8)
        received = []
        result_handle = 2**41 + 0x5678
        factory = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
        signature = factory(ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p)

        def receiver(format, handle):
            received.append((format, handle))
            return result_handle

        # Separate caller/callee ctypes objects share an actual native callback
        # address. A bad caller argtype must not also change the receiver ABI.
        native = signature(receiver)
        caller = signature(ctypes.cast(native, ctypes.c_void_p).value)
        user, kernel = MagicMock(), MagicMock()
        user.SetClipboardData = caller
        api = windows.Win32API(loader=lambda name, **options: user if name == "user32.dll" else kernel)
        return api, received, result_handle, native  # Keep callback alive.

    def assert_native_handles(self, api, received, result_handle):
        received.clear()
        handle = 2**40 + 0x1234
        result = api.SetClipboardData(windows.CF_UNICODETEXT, handle)
        self.assertEqual(received, [(windows.CF_UNICODETEXT, handle)])
        self.assertEqual(result, result_handle)

    def test_handles_cross_a_real_ctypes_boundary_without_32bit_truncation(self):
        api, received, result, native = self.make_native_boundary()
        self.assert_native_handles(api, received, result)

    def test_native_boundary_detects_c_int32_argument_and_return_regressions(self):
        for field in ("argtypes", "restype"):
            with self.subTest(field=field):
                api, received, result, native = self.make_native_boundary()
                if field == "argtypes":
                    api.SetClipboardData.argtypes = [ctypes.c_uint32, ctypes.c_int32]
                else:
                    api.SetClipboardData.restype = ctypes.c_int32
                with self.assertRaises(AssertionError):
                    self.assert_native_handles(api, received, result)
