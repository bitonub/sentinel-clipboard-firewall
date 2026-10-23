"""Synthetic, offscreen QtTest tests. Never use the system clipboard."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

# Select a virtual platform before Qt is imported, even in a Wayland session.
os.environ["QT_QPA_PLATFORM"] = "offscreen"
try:
    from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QMimeData, QTimer, Qt
    from PySide6.QtGui import QInputMethodEvent, QTextCursor
    from PySide6.QtTest import QSignalSpy, QTest
    from PySide6.QtWidgets import QApplication
    from sentinel.gui.window import Window
    from sentinel.gui.worker import Worker, analyze
    QT_AVAILABLE = True
except ModuleNotFoundError as error:
    if error.name != "PySide6":
        raise
    QT_AVAILABLE = False

from sentinel.core.sanitize import sanitize
from sentinel.limits import InputError, MAX_INPUT_BYTES, utf8_size


@unittest.skipUnless(QT_AVAILABLE, "Instala el extra GUI para ejecutar QtTest.")
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["sentinel-gui-tests"])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.assertEqual(self.app.platformName(), "offscreen")
        self.window = Window()
        self.window.show()
        self.gates = []

    def tearDown(self):
        for gate in self.gates:
            gate.set()
        self.until(lambda: not self.window.busy)
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def until(self, condition, timeout=10):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            loop = QEventLoop()
            QTimer.singleShot(10, loop.quit)
            loop.exec()
        self.assertTrue(condition(), "Qt operation did not finish within the test deadline")

    def run_action(self, button):
        QTest.mouseClick(button, Qt.LeftButton)
        self.until(lambda: not self.window.busy)
        return self.window.output.toPlainText()

    def block_analysis(self, *, error=False):
        entered, release = threading.Event(), threading.Event()
        self.gates.append(release)

        def blocked(*args):
            entered.set()
            if not release.wait(8):
                raise RuntimeError("Synthetic worker test deadline")
            if error:
                raise RuntimeError("SYNTHETIC_PRIVATE_MARKER")
            return analyze(*args)

        patcher = patch("sentinel.gui.worker.analyze", side_effect=blocked)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        self.window.start("scan")
        self.until(entered.is_set)
        return release, mock

    def test_plain_text_labels_and_read_only_output(self):
        self.assertEqual([b.text() for b in self.window._action_buttons()],
                         ["Inspeccionar", "Sanitizar", "Analizar comando"])
        self.assertTrue(self.window.output.isReadOnly())
        self.assertFalse(self.window.input.isUndoRedoEnabled())
        text = "<b>synthetic</b>\npassword=Example42"
        self.window.input.setPlainText(text)
        self.assertEqual(self.run_action(self.window.sanitize_button), sanitize(text))
        self.assertIn("<b>synthetic</b>", self.window.output.toPlainText())

    def test_tab_navigation_follows_complete_cycle_after_button_click(self):
        order = (self.window.inspect_button, self.window.sanitize_button,
                 self.window.command_button, self.window.shell,
                 self.window.clear_button, self.window.input, self.window.output)
        self.window.input.setPlainText("synthetic input")
        self.window.output.setPlainText("synthetic output")
        # Isolate navigation from the temporary disabling of busy controls.
        with patch.object(self.window, "start"):
            QTest.mouseClick(self.window.inspect_button, Qt.LeftButton)
        self.until(self.window.inspect_button.hasFocus)
        for expected in order[1:] + order[:1]:
            QTest.keyClick(self.app.focusWidget(), Qt.Key_Tab)
            self.assertIs(self.app.focusWidget(), expected)
        self.assertEqual(self.window.input.toPlainText(), "synthetic input")
        self.assertEqual(self.window.output.toPlainText(), "synthetic output")

    def test_shift_tab_navigation_follows_complete_reverse_cycle(self):
        order = (self.window.output, self.window.input, self.window.clear_button,
                 self.window.shell, self.window.command_button,
                 self.window.sanitize_button, self.window.inspect_button)
        self.window.input.setPlainText("synthetic input")
        self.window.output.setPlainText("synthetic output")
        with patch.object(self.window, "start"):
            QTest.mouseClick(self.window.inspect_button, Qt.LeftButton)
        self.until(self.window.inspect_button.hasFocus)
        for expected in order:
            QTest.keyClick(self.app.focusWidget(), Qt.Key_Tab, Qt.ShiftModifier)
            self.assertIs(self.app.focusWidget(), expected)
        self.assertEqual(self.window.input.toPlainText(), "synthetic input")
        self.assertEqual(self.window.output.toPlainText(), "synthetic output")

    def test_tab_navigation_still_works_after_real_inspection(self):
        order = (self.window.inspect_button, self.window.sanitize_button,
                 self.window.command_button, self.window.shell,
                 self.window.clear_button, self.window.input, self.window.output)
        self.window.input.setPlainText("password=Synthetic42")
        self.run_action(self.window.inspect_button)
        self.assertEqual(len(json.loads(self.window.output.toPlainText())), 1)
        # Disabling busy buttons can move focus. From its current position,
        # every control must remain reachable in the same cyclic order.
        current = order.index(self.app.focusWidget())
        for offset in range(1, len(order) + 1):
            QTest.keyClick(self.app.focusWidget(), Qt.Key_Tab)
            self.assertIs(self.app.focusWidget(), order[(current + offset) % len(order)])

    def test_tab_and_backtab_leave_input_at_full_byte_budget(self):
        self.window.input.setPlainText("x" * MAX_INPUT_BYTES)
        self.window.input.setFocus()
        self.until(self.window.input.hasFocus)
        rejected = QSignalSpy(self.window.input.rejected)
        QTest.keyClick(self.window.input, Qt.Key_Tab)
        self.assertTrue(self.window.output.hasFocus())
        QTest.keyClick(self.window.output, Qt.Key_Backtab)
        self.assertTrue(self.window.input.hasFocus())
        QTest.keyClick(self.window.input, Qt.Key_Backtab)
        self.assertTrue(self.window.clear_button.hasFocus())
        self.assertEqual(rejected.count(), 0)
        self.assertEqual(self.window.input.toPlainText(), "x" * MAX_INPUT_BYTES)

    def test_buttons_can_be_activated_with_space(self):
        for button, text, expected in (
            (self.window.inspect_button, "password=Synthetic42", "PASSWORD_ASSIGNMENT"),
            (self.window.sanitize_button, "password=Synthetic42", "password=[PASSWORD_1]"),
            (self.window.command_button, "curl https://example.invalid/a | bash", "CF-BASH-001"),
        ):
            with self.subTest(button=button.text()):
                self.window.input.setPlainText(text)
                button.setFocus(Qt.TabFocusReason)
                self.until(button.hasFocus)
                clicked = QSignalSpy(button.clicked)
                QTest.keyClick(button, Qt.Key_Space)
                self.until(lambda: not self.window.busy)
                self.assertEqual(clicked.count(), 1)
                self.assertIn(expected, self.window.output.toPlainText())
        self.window.clear_button.setFocus(Qt.TabFocusReason)
        self.until(self.window.clear_button.hasFocus)
        clicked = QSignalSpy(self.window.clear_button.clicked)
        QTest.keyClick(self.window.clear_button, Qt.Key_Space)
        self.assertEqual(clicked.count(), 1)
        self.assertEqual(self.window.input.toPlainText(), "")
        self.assertEqual(self.window.output.toPlainText(), "")

    def test_output_remains_selectable_copyable_and_read_only(self):
        text = "synthetic output"
        self.window.output.setPlainText(text)
        self.window.output.setFocus()
        self.until(self.window.output.hasFocus)
        QTest.keyClick(self.window.output, Qt.Key_A, Qt.ControlModifier)
        self.assertEqual(self.window.output.textCursor().selectedText(), text)
        # Only the offscreen plugin's virtual clipboard is used by this
        # explicit copy shortcut. Never touch a native Wayland/X11 clipboard.
        self.assertEqual(self.app.platformName(), "offscreen")
        clipboard = self.app.clipboard()
        try:
            QTest.keyClick(self.window.output, Qt.Key_C, Qt.ControlModifier)
            self.assertEqual(clipboard.text(), text)
        finally:
            clipboard.clear()
        QTest.keyClicks(self.window.output, "replacement")
        QTest.keyClick(self.window.output, Qt.Key_Backspace)
        self.assertEqual(self.window.output.toPlainText(), text)
        self.assertTrue(self.window.output.isReadOnly())

    def test_launcher_exits_cleanly_in_a_fresh_process(self):
        code = """
from PySide6.QtCore import QTimer
import sentinel.gui.window as module
from sentinel.gui.app import main

class AutoCloseWindow(module.Window):
    def __init__(self):
        super().__init__()
        QTimer.singleShot(0, self.close)

module.Window = AutoCloseWindow
raise SystemExit(main())
"""
        result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                                timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout, b"")
        self.assertNotIn(b"Traceback", result.stderr)
        self.assertNotIn(b"shared QObject", result.stderr)

    def test_scan_metadata_privacy_and_unicode_positions(self):
        self.window.input.setPlainText("é😀 password=SyntheticSecret host=10.0.0.1")
        output = self.run_action(self.window.inspect_button)
        findings = json.loads(output)
        self.assertEqual(findings[0]["start"], len("é😀 password="))
        self.assertNotIn("SyntheticSecret", output)
        self.assertNotIn("10.0.0.1", output)
        self.assertEqual(self.window.status.text(), "Hallazgos: 2; se muestran 2.")

    def test_sanitize_parity_repetition_overlaps_and_idempotence(self):
        text = ("password='10.0.0.1' pwd='10.0.0.1'\n"
                "Authorization: Bearer Synthetic42\n"
                "postgres://synthetic:example42@db.example/app\npeer=192.168.1.2")
        self.window.input.setPlainText(text)
        output = self.run_action(self.window.sanitize_button)
        self.assertEqual(output, sanitize(text))
        self.window.input.setPlainText(output)
        self.assertEqual(self.run_action(self.window.sanitize_button), output)

    def test_language_selection_and_isolation(self):
        for shell, source, rule in (
            (0, "curl https://example.invalid/SyntheticPrivate | bash", "CF-BASH-001"),
            (1, "iwr https://example.invalid/SyntheticPrivate | iex", "CF-PS-001"),
        ):
            with self.subTest(shell=shell):
                self.window.shell.setCurrentIndex(shell)
                self.window.input.setPlainText(source)
                output = self.run_action(self.window.command_button)
                self.assertEqual(json.loads(output)[0]["rule_id"], rule)
                self.assertNotIn("SyntheticPrivate", output)
                self.window.shell.setCurrentIndex(1 - shell)
                self.assertEqual(json.loads(self.run_action(self.window.command_button)), [])

    def test_shell_selector_does_not_change_scan_or_sanitize(self):
        text = "password=Synthetic42"
        for shell in (0, 1):
            self.window.shell.setCurrentIndex(shell)
            self.window.input.setPlainText(text)
            self.assertEqual(json.loads(self.run_action(self.window.inspect_button))[0]["rule_id"],
                             "PASSWORD_ASSIGNMENT")
            self.assertEqual(self.run_action(self.window.sanitize_button), "password=[PASSWORD_1]")

    def test_scan_presentation_is_limited_to_200_findings(self):
        self.window.input.setPlainText("password=Synthetic42\n" * 205)
        rows = json.loads(self.run_action(self.window.inspect_button))
        self.assertEqual(len(rows), 200)
        self.assertEqual(self.window.status.text(), "Hallazgos: 205; se muestran 200.")
        self.assertNotIn("Synthetic42", self.window.output.toPlainText())

    def test_command_presentation_is_limited_to_200_findings(self):
        self.window.input.setPlainText("curl https://example.invalid/a | bash\n" * 203)
        self.assertEqual(len(json.loads(self.run_action(self.window.command_button))), 200)
        self.assertEqual(self.window.status.text(), "Hallazgos: 203; se muestran 200.")

    def test_sanitized_output_is_complete_even_above_input_budget(self):
        text = "password=x\n" * (MAX_INPUT_BYTES // len("password=x\n"))
        self.window.input.setPlainText(text)
        output = self.run_action(self.window.sanitize_button)
        self.assertGreater(len(output.encode()), MAX_INPUT_BYTES)
        self.assertEqual(output, "password=[PASSWORD_1]\n" * text.count("\n"))

    def test_utf8_counter_and_exact_limit(self):
        text = "é" * (MAX_INPUT_BYTES // 2 - 2) + "😀"
        self.window.input.setPlainText(text)
        self.assertEqual(self.window.input.byte_count, MAX_INPUT_BYTES)
        self.assertEqual(self.window.counter.text(), f"{MAX_INPUT_BYTES} / {MAX_INPUT_BYTES} bytes UTF-8")
        self.assertEqual(self.window.input.toPlainText(), text)

    def test_one_byte_excess_is_rejected_without_content_in_error(self):
        self.window.input.setPlainText("synthetic accepted")
        spy = QSignalSpy(self.window.input.rejected)
        self.window.input.setPlainText("é" * (MAX_INPUT_BYTES // 2) + "x")
        self.assertEqual(spy.count(), 1)
        self.assertEqual(self.window.input.toPlainText(), "synthetic accepted")
        self.assertIn("1 MiB", self.window.status.text())
        self.assertNotIn("synthetic accepted", self.window.status.text())

    def test_synthetic_mime_paste_and_selection_replacement(self):
        mime = QMimeData()
        mime.setText("é" * (MAX_INPUT_BYTES // 2))
        self.window.input.insertFromMimeData(mime)
        self.assertEqual(self.window.input.byte_count, MAX_INPUT_BYTES)
        mime.setText("SyntheticPrivate")
        self.window.input.insertFromMimeData(mime)
        self.assertEqual(self.window.input.byte_count, MAX_INPUT_BYTES)
        self.window.input.selectAll()
        self.window.input.insertFromMimeData(mime)
        self.assertEqual(self.window.input.toPlainText(), "SyntheticPrivate")

    def test_keyboard_enforces_limit_and_still_allows_deletion(self):
        self.window.input.setPlainText("x" * MAX_INPUT_BYTES)
        self.window.input.moveCursor(QTextCursor.End)
        QTest.keyClicks(self.window.input, "A")
        self.assertEqual(self.window.input.byte_count, MAX_INPUT_BYTES)
        QTest.keyClick(self.window.input, Qt.Key_Backspace)
        self.assertEqual(self.window.input.byte_count, MAX_INPUT_BYTES - 1)
        QTest.keyClicks(self.window.input, "B")
        self.assertTrue(self.window.input.toPlainText().endswith("B"))

    def test_ime_commit_cannot_exceed_limit(self):
        self.window.input.setPlainText("x" * (MAX_INPUT_BYTES - 1))
        self.window.input.moveCursor(QTextCursor.End)
        event = QInputMethodEvent()
        event.setCommitString("é")
        QApplication.sendEvent(self.window.input, event)
        self.assertEqual(self.window.input.byte_count, MAX_INPUT_BYTES - 1)
        self.assertEqual(self.window.input.toPlainText(), "x" * (MAX_INPUT_BYTES - 1))

    def test_cursor_insertion_cannot_bypass_budget(self):
        self.window.input.setPlainText("x" * MAX_INPUT_BYTES)
        self.window.input.textCursor().insertText("SyntheticPrivate")
        self.assertEqual(self.window.input.byte_count, MAX_INPUT_BYTES)
        self.assertNotIn("SyntheticPrivate", self.window.input.toPlainText())

    def test_invalid_unicode_error_is_static(self):
        self.window.input.setPlainText("synthetic accepted")
        self.window.input.setPlainText("SyntheticPrivate\ud800")
        self.assertEqual(self.window.input.toPlainText(), "synthetic accepted")
        self.assertEqual(self.window.status.text(), "La entrada no es UTF-8 válido.")

    def test_changing_input_clears_previous_results(self):
        self.window.input.setPlainText("password=Synthetic42")
        self.run_action(self.window.sanitize_button)
        QTest.keyClicks(self.window.input, "x")
        self.assertEqual(self.window.output.toPlainText(), "")
        QTest.mouseClick(self.window.clear_button, Qt.LeftButton)
        self.assertEqual(self.window.input.toPlainText(), "")

    def test_pending_result_for_old_input_is_discarded(self):
        self.window.input.setPlainText("password=Synthetic42")
        release, _ = self.block_analysis()
        self.window.input.setPlainText("new synthetic input")
        release.set()
        self.until(lambda: not self.window.busy)
        self.assertEqual(self.window.output.toPlainText(), "")
        self.assertNotIn("Hallazgos:", self.window.status.text())

    def test_pending_error_for_old_input_is_discarded(self):
        self.window.input.setPlainText("password=Synthetic42")
        release, _ = self.block_analysis(error=True)
        self.window.input.clear()
        release.set()
        self.until(lambda: not self.window.busy)
        self.assertNotIn("Error:", self.window.status.text())
        self.assertEqual(self.window.output.toPlainText(), "")

    def test_only_one_operation_can_run(self):
        release, mocked = self.block_analysis()
        for button in self.window._action_buttons():
            self.assertFalse(button.isEnabled())
            QTest.mouseClick(button, Qt.LeftButton)
        self.window.start("sanitize")
        self.assertEqual(mocked.call_count, 1)
        release.set()
        self.until(lambda: not self.window.busy)
        self.assertTrue(all(b.isEnabled() for b in self.window._action_buttons()))

    def test_close_with_pending_work_keeps_event_loop_responsive(self):
        release, _ = self.block_analysis()
        finished = QSignalSpy(self.window._thread.finished)
        self.assertFalse(self.window.close())
        self.assertTrue(self.window.isVisible())
        self.assertTrue(self.window.busy)
        callbacks = []
        QTimer.singleShot(0, lambda: callbacks.append(True))
        self.until(lambda: bool(callbacks))
        release.set()
        self.until(lambda: not self.window.isVisible())
        self.assertFalse(self.window.busy)
        self.assertEqual(finished.count(), 1)

    def test_worker_exception_does_not_expose_content_or_traceback(self):
        self.window.input.setPlainText("password=SyntheticPrivate")
        out, err = io.StringIO(), io.StringIO()
        with patch("sentinel.gui.worker.analyze", side_effect=RuntimeError("SyntheticPrivate")), \
             redirect_stdout(out), redirect_stderr(err):
            self.run_action(self.window.inspect_button)
        self.assertEqual(self.window.status.text(), "Error: no se pudo completar la operación.")
        self.assertEqual(self.window.output.toPlainText(), "")
        self.assertEqual(out.getvalue() + err.getvalue(), "")

    def test_actual_syntax_errors_are_safe_for_both_shells(self):
        for shell in (0, 1):
            self.window.shell.setCurrentIndex(shell)
            self.window.input.setPlainText('"SyntheticPrivate')
            self.run_action(self.window.command_button)
            self.assertEqual(self.window.status.text(), "Error: no se pudo analizar la sintaxis del comando.")
            self.assertEqual(self.window.output.toPlainText(), "")

    def test_worker_start_failure_is_safe_and_recovers_controls(self):
        self.window.input.setPlainText("password=SyntheticPrivate")
        error = io.StringIO()
        with patch("sentinel.gui.window.Worker", side_effect=RuntimeError("SyntheticPrivate")), \
             redirect_stderr(error):
            QTest.mouseClick(self.window.inspect_button, Qt.LeftButton)
        self.assertFalse(self.window.busy)
        self.assertTrue(self.window.inspect_button.isEnabled())
        self.assertEqual(self.window.status.text(), "Error: no se pudo iniciar la operación.")
        self.assertEqual(error.getvalue(), "")

    def test_presentation_failure_is_safe(self):
        self.window.input.setPlainText("password=SyntheticPrivate")
        error = io.StringIO()
        with patch.object(self.window.output, "setPlainText", side_effect=RuntimeError("SyntheticPrivate")), \
             redirect_stderr(error):
            self.run_action(self.window.sanitize_button)
        self.assertEqual(self.window.output.toPlainText(), "")
        self.assertEqual(self.window.status.text(), "Error: no se pudo presentar el resultado.")
        self.assertEqual(error.getvalue(), "")

    def test_worker_revalidates_input_and_releases_its_reference(self):
        worker = Worker(42, "x" * (MAX_INPUT_BYTES + 1), "scan", "bash")
        failed, finished = QSignalSpy(worker.failed), QSignalSpy(worker.finished)
        with patch("sentinel.gui.worker.scan") as scan_mock:
            worker.start()
            self.until(lambda: worker.wait(0))
        scan_mock.assert_not_called()
        self.assertEqual(failed.count(), 1)
        self.assertEqual(finished.count(), 1)
        self.assertEqual(worker._text, "")
        self.assertNotIn("xxx", failed.at(0)[1])


class InputBudgetTests(unittest.TestCase):
    def test_shared_budget_counts_bytes_not_characters(self):
        for char in ("x", "é", "😀"):
            with self.subTest(char=char):
                text = char * (MAX_INPUT_BYTES // len(char.encode()))
                self.assertEqual(utf8_size(text), MAX_INPUT_BYTES)
                with self.assertRaises(InputError):
                    utf8_size(text + "x")


if __name__ == "__main__":
    unittest.main()
