"""Plain text input with a UTF-8 budget and no undo history."""

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QPlainTextEdit

from sentinel.limits import InputError, MAX_INPUT_BYTES, utf8_size


class InputEditor(QPlainTextEdit):
    acceptedChanged = Signal()
    rejected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setUndoRedoEnabled(False)
        self.setAcceptDrops(False)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._accepted_text = ""  # Current accepted document, not a history.
        self.byte_count = 0
        self.textChanged.connect(self._validate_document)

    def _validate_document(self):
        text = self.toPlainText()
        try:
            size = utf8_size(text)
        except InputError as error:
            # Covers IME commits, QTextCursor edits and other Qt insertion paths.
            position = self.textCursor().position()
            with QSignalBlocker(self):
                super().setPlainText(self._accepted_text)
                cursor = self.textCursor()
                cursor.setPosition(min(position, self.document().characterCount() - 1))
                self.setTextCursor(cursor)
            self.rejected.emit(str(error))
            return
        self._accepted_text = text
        self.byte_count = size
        self.acceptedChanged.emit()

    def setPlainText(self, text: str):
        try:
            utf8_size(text)
        except InputError as error:
            self.rejected.emit(str(error))
            return
        super().setPlainText(text)

    def _allows_insert(self, text: str) -> bool:
        try:
            # QTextCursor uses paragraph separators in selectedText().
            selected = self.textCursor().selectedText().replace("\u2029", "\n")
            incoming = text.replace("\r\n", "\n").replace("\r", "\n")
            size = self.byte_count - utf8_size(selected) + utf8_size(incoming)
            if size > MAX_INPUT_BYTES:
                raise InputError("La entrada supera 1 MiB UTF-8.")
        except InputError as error:
            self.rejected.emit(str(error))
            return False
        return True

    def insertPlainText(self, text: str):
        if self._allows_insert(text):
            super().insertPlainText(text)

    def canInsertFromMimeData(self, source):
        return source.hasText()

    def insertFromMimeData(self, source):
        # Only an explicit user paste reaches here; never query QClipboard.
        if source.hasText():
            self.insertPlainText(source.text())

    def keyPressEvent(self, event: QKeyEvent):
        from PySide6.QtCore import Qt

        if self.tabChangesFocus() and event.key() in (Qt.Key_Tab, Qt.Key_Backtab):
            # Focus navigation must also work when the byte budget is full.
            super().keyPressEvent(event)
            return
        editing_shortcut = event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)
        deleting = event.key() in (Qt.Key_Backspace, Qt.Key_Delete)
        if event.text() and not editing_shortcut and not deleting:
            if not self._allows_insert(event.text()):
                event.accept()
                return
        super().keyPressEvent(event)
