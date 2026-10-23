from contextlib import redirect_stderr, redirect_stdout
import io
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from sentinel import cli
from sentinel.adapters import wayland


class ClipboardTests(unittest.TestCase):
    def setUp(self):
        self.data = io.BytesIO("α password=SYNTHETIC_SECRET_MARKER host=10.0.0.1\n".encode())
        self.read_sizes = []
        self.process = MagicMock()
        self.process.stdin = None
        self.process.stderr = None
        self.process.stdout.fileno.return_value = 42
        self.process.wait.return_value = 0
        self.process.poll.return_value = 0
        self.writer = MagicMock()
        self.writer.stdout = None
        self.writer.stderr = None
        self.writer.returncode = 0
        self.writer.poll.return_value = 0
        self.writer.communicate.return_value = (None, None)
        self.copy = MagicMock(return_value=self.writer)
        self.popen = self.enterContext(patch("sentinel.adapters.wayland.subprocess.Popen", side_effect=self.start_process))
        self.run = self.enterContext(patch("sentinel.adapters.wayland.subprocess.run", side_effect=AssertionError("subprocess.run must not be used")))
        selector = MagicMock()
        selector.select.return_value = [(None, wayland.selectors.EVENT_READ)]
        self.selector = selector
        selector_factory = self.enterContext(patch("sentinel.adapters.wayland.selectors.DefaultSelector"))
        selector_factory.return_value = selector
        self.read = self.enterContext(patch("sentinel.adapters.wayland.os.read", side_effect=self.read_chunk))

    def start_process(self, command, **options):
        if command == wayland.PASTE_COMMAND:
            return self.process
        self.assertEqual(command, wayland.COPY_COMMAND)
        return self.copy(command, **options)

    def assert_waits_bounded(self, process, maximum):
        for call in process.wait.call_args_list:
            self.assertEqual(call.args, ())
            self.assertGreater(call.kwargs["timeout"], 0)
            self.assertLessEqual(call.kwargs["timeout"], maximum)

    def read_chunk(self, fd, size):
        self.assertEqual(fd, 42)
        self.assertGreater(size, 0)
        self.read_sizes.append(size)
        return self.data.read(size)

    def invoke(self, arguments=None):
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["sentinel"] + (arguments or ["clipboard", "sanitize"])), \
             patch("sentinel.cli.sys.stdin") as stdin, redirect_stdout(out), redirect_stderr(err):
            code = cli.main()
            stdin.buffer.read.assert_not_called()
        self.assertNotIn("SYNTHETIC_SECRET_MARKER", out.getvalue() + err.getvalue())
        self.assertNotIn("[PASSWORD_", out.getvalue() + err.getvalue())
        self.assertNotIn("10.0.0.1", out.getvalue() + err.getvalue())
        self.assertNotIn("Traceback", out.getvalue() + err.getvalue())
        return code, out.getvalue(), err.getvalue()

    def assert_prewrite_failure(self):
        code, out, err = self.invoke()
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("Error:"))
        self.copy.assert_not_called()

    def test_success_fixed_commands_and_stdin_only_payload(self):
        self.assertEqual(self.invoke(), (0, "Portapapeles actualizado; hallazgos: 2.\n", ""))
        self.assertEqual(self.popen.call_count, 2)
        self.assertEqual(self.popen.call_args_list[0].args, (wayland.PASTE_COMMAND,))
        self.assertEqual(self.popen.call_args_list[0].kwargs, dict(
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, shell=False, bufsize=0,
        ))
        self.copy.assert_called_once_with(
            ("wl-copy", "--type", "text/plain;charset=utf-8", "--sensitive"),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False,
            bufsize=0,
        )
        self.writer.communicate.assert_called_once_with(
            input="α password=[PASSWORD_1] host=[PRIVATE_IP_1]\n".encode(), timeout=wayland.TOOL_TIMEOUT,
        )
        self.assert_waits_bounded(self.process, wayland.TOOL_TIMEOUT)
        self.process.stdout.close.assert_called_once()
        self.writer.stdin.close.assert_called_once()
        self.selector.close.assert_called_once()
        self.run.assert_not_called()

    def test_unchanged_text_is_not_rewritten(self):
        self.data = io.BytesIO(b"synthetic public text\n")
        self.assertEqual(self.invoke(), (0, "Sin cambios; hallazgos: 0.\n", ""))
        self.copy.assert_not_called()

    def test_wl_paste_absent(self):
        self.popen.side_effect = FileNotFoundError("SYNTHETIC_SECRET_MARKER")
        self.assert_prewrite_failure()

    def test_wl_copy_absent(self):
        self.copy.side_effect = FileNotFoundError("SYNTHETIC_SECRET_MARKER")
        code, out, err = self.invoke()
        self.assertEqual((code, out), (2, ""))
        self.assertIn("wl-copy", err)

    def test_read_exit_failure_discards_partial_output(self):
        self.process.wait.return_value = 1
        self.assert_prewrite_failure()

    def test_read_io_failure(self):
        self.read.side_effect = OSError("SYNTHETIC_SECRET_MARKER")
        self.assert_prewrite_failure()

    def test_write_failure_does_not_echo_tool_output(self):
        self.writer.returncode = 1
        self.writer.poll.return_value = 1
        code, out, err = self.invoke()
        self.assertEqual((code, out), (2, ""))
        self.assertIn("escribir", err)

    def test_invalid_utf8(self):
        self.data = io.BytesIO(b"SYNTHETIC_SECRET_MARKER\xff")
        self.assert_prewrite_failure()

    def test_exact_byte_limit_is_accepted(self):
        self.data = io.BytesIO(("é" * (wayland.MAX_INPUT_BYTES // 2)).encode())
        self.assertEqual(self.invoke(), (0, "Sin cambios; hallazgos: 0.\n", ""))
        self.assertEqual(self.data.tell(), wayland.MAX_INPUT_BYTES)
        self.copy.assert_not_called()

    def test_oversized_stream_stops_at_limit_plus_one(self):
        self.data = io.BytesIO(b"x" * (wayland.MAX_INPUT_BYTES * 2))
        self.process.poll.return_value = None
        self.assert_prewrite_failure()
        self.assertEqual(self.data.tell(), wayland.MAX_INPUT_BYTES + 1)
        self.assertLessEqual(max(self.read_sizes), 65536)
        self.assertEqual(sum(self.read_sizes), wayland.MAX_INPUT_BYTES + 1)
        self.process.kill.assert_called_once()
        self.assert_waits_bounded(self.process, wayland.CLEANUP_TIMEOUT)

    def test_read_timeout_kills_and_reaps_process(self):
        self.selector.select.return_value = []
        self.process.poll.return_value = None
        self.assert_prewrite_failure()
        self.process.kill.assert_called_once()
        self.assert_waits_bounded(self.process, wayland.CLEANUP_TIMEOUT)

    def test_wait_timeout_after_eof(self):
        self.process.wait.side_effect = [subprocess.TimeoutExpired(wayland.PASTE_COMMAND, 5, stderr=b"SYNTHETIC_SECRET_MARKER"), 0]
        self.process.poll.return_value = None
        self.assert_prewrite_failure()
        self.process.kill.assert_called_once()

    def test_write_timeout(self):
        self.writer.communicate.side_effect = subprocess.TimeoutExpired(wayland.COPY_COMMAND, 5, stderr=b"SYNTHETIC_SECRET_MARKER")
        self.writer.poll.return_value = None
        code, out, err = self.invoke()
        self.assertEqual((code, out), (2, ""))
        self.assertIn("agotado", err)
        self.writer.kill.assert_called_once()
        self.writer.wait.assert_called_once()
        self.assert_waits_bounded(self.writer, wayland.CLEANUP_TIMEOUT)
        self.writer.stdin.close.assert_called_once()

    def test_read_close_failure_is_a_safe_prewrite_error(self):
        self.process.stdout.close.side_effect = OSError("SYNTHETIC_SECRET_MARKER")
        self.assert_prewrite_failure()
        self.process.stdout.close.assert_called_once()
        self.selector.close.assert_called_once()

    def test_selector_close_failure_is_safe_and_still_closes_pipe(self):
        self.selector.close.side_effect = OSError("SYNTHETIC_SECRET_MARKER")
        self.assert_prewrite_failure()
        self.process.stdout.close.assert_called_once()

    def test_cleanup_failures_do_not_hide_primary_read_error(self):
        self.process.wait.return_value = 1
        self.process.stdout.close.side_effect = OSError("SYNTHETIC_SECRET_MARKER")
        self.selector.close.side_effect = OSError("SYNTHETIC_SECRET_MARKER")
        code, out, err = self.invoke()
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "Error: No se pudo leer el portapapeles.\n")
        self.copy.assert_not_called()

    def test_write_close_failure_does_not_report_success(self):
        self.writer.stdin.close.side_effect = OSError("SYNTHETIC_SECRET_MARKER")
        code, out, err = self.invoke()
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "Error: No se pudo finalizar la escritura del portapapeles.\n")
        self.writer.communicate.assert_called_once()

    def test_writer_not_terminated_after_kill_returns_without_retrying(self):
        self.writer.communicate.side_effect = subprocess.TimeoutExpired(wayland.COPY_COMMAND, 5)
        self.writer.poll.return_value = None
        self.writer.wait.side_effect = subprocess.TimeoutExpired(wayland.COPY_COMMAND, wayland.CLEANUP_TIMEOUT)
        self.writer.stdin.close.side_effect = OSError("SYNTHETIC_SECRET_MARKER")
        code, out, err = self.invoke()
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "Error: Tiempo de escritura del portapapeles agotado.\n")
        self.writer.communicate.assert_called_once()
        self.writer.kill.assert_called_once()
        self.writer.wait.assert_called_once()
        self.assert_waits_bounded(self.writer, wayland.CLEANUP_TIMEOUT)
        self.writer.stdin.close.assert_called_once()

    def test_reader_not_terminated_after_kill_still_closes_resources(self):
        self.selector.select.return_value = []
        self.process.poll.return_value = None
        self.process.wait.side_effect = subprocess.TimeoutExpired(wayland.PASTE_COMMAND, wayland.CLEANUP_TIMEOUT)
        self.assert_prewrite_failure()
        self.process.kill.assert_called_once()
        self.process.wait.assert_called_once()
        self.assert_waits_bounded(self.process, wayland.CLEANUP_TIMEOUT)
        self.process.stdout.close.assert_called_once()
        self.selector.close.assert_called_once()

    def test_kill_failure_still_attempts_bounded_wait_and_close(self):
        self.writer.communicate.side_effect = subprocess.TimeoutExpired(wayland.COPY_COMMAND, 5)
        self.writer.poll.return_value = None
        self.writer.kill.side_effect = OSError("SYNTHETIC_SECRET_MARKER")
        code, out, err = self.invoke()
        self.assertEqual((code, out), (2, ""))
        self.assertIn("agotado", err)
        self.writer.wait.assert_called_once()
        self.assert_waits_bounded(self.writer, wayland.CLEANUP_TIMEOUT)
        self.writer.stdin.close.assert_called_once()

    def test_sanitizer_failure_prevents_copy(self):
        with patch("sentinel.adapters.wayland.sanitize", side_effect=RuntimeError("SYNTHETIC_SECRET_MARKER")):
            self.assert_prewrite_failure()

    def test_scan_failure_prevents_copy(self):
        with patch("sentinel.adapters.wayland.scan", side_effect=RuntimeError("SYNTHETIC_SECRET_MARKER")):
            self.assert_prewrite_failure()

    def test_clipboard_syntax_is_validated_before_reading(self):
        with patch("sys.argv", ["sentinel", "clipboard"]), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                cli.main()
        self.assertEqual(caught.exception.code, 2)
        self.popen.assert_not_called()
        self.copy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
