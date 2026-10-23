"""Minimal explicit-action GUI; no clipboard integration or persistence."""

from PySide6.QtCore import QTimer, Slot
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMainWindow, QPlainTextEdit,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from sentinel.gui.editor import InputEditor
from sentinel.gui.worker import Result, Worker
from sentinel.limits import InputError, MAX_INPUT_BYTES, utf8_size


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SENTINEL")
        self.resize(960, 720)
        self._thread = None
        self._worker = None
        self._revision = 0
        self._job = 0
        self._job_revision = 0
        self._closing = False

        self.input = InputEditor()
        self.input.setTabChangesFocus(True)
        self.input.setAccessibleName("Entrada")
        self.input.setPlaceholderText("Introduce texto para inspeccionar o un comando para analizar.")
        self.output = QPlainTextEdit()
        self.output.setAccessibleName("Salida")
        self.output.setReadOnly(True)
        self.output.setTabChangesFocus(True)
        self.output.setUndoRedoEnabled(False)
        self.output.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.counter = QLabel()
        self.status = QLabel("Listo.")
        self.status.setTextFormat(Qt.PlainText)
        self.shell = QComboBox()
        self.shell.addItem("Bash", "bash")
        self.shell.addItem("PowerShell", "powershell")
        self.shell.setAccessibleName("Lenguaje solo para Analizar comando")
        self.inspect_button = QPushButton("Inspeccionar")
        self.sanitize_button = QPushButton("Sanitizar")
        self.command_button = QPushButton("Analizar comando")
        self.clear_button = QPushButton("Limpiar")
        actions = QHBoxLayout()
        for button in self._action_buttons():
            actions.addWidget(button)
        actions.addWidget(QLabel("Lenguaje (solo comandos):"))
        actions.addWidget(self.shell)
        actions.addStretch()
        actions.addWidget(self.clear_button)

        entry = QWidget()
        entry_layout = QVBoxLayout(entry)
        entry_layout.addWidget(QLabel("Entrada"))
        entry_layout.addWidget(self.input)
        entry_layout.addWidget(self.counter)
        result = QWidget()
        result_layout = QVBoxLayout(result)
        result_layout.addWidget(QLabel("Salida (solo lectura)"))
        result_layout.addWidget(self.output)
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(entry)
        splitter.addWidget(result)
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(actions)
        layout.addWidget(splitter)
        layout.addWidget(self.status)
        notice = QLabel("Solo se cubren las reglas implementadas. Sin hallazgos no significa seguro.")
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.setCentralWidget(central)

        focus_order = (
            self.inspect_button, self.sanitize_button, self.command_button,
            self.shell, self.clear_button, self.input, self.output,
        )
        for widget in focus_order:
            widget.setFocusPolicy(Qt.StrongFocus)
        for previous, following in zip(focus_order, focus_order[1:]):
            QWidget.setTabOrder(previous, following)

        self.input.acceptedChanged.connect(self._input_changed)
        self.input.rejected.connect(self.status.setText)
        self.inspect_button.clicked.connect(lambda: self.start("scan"))
        self.sanitize_button.clicked.connect(lambda: self.start("sanitize"))
        self.command_button.clicked.connect(lambda: self.start("check-command"))
        self.clear_button.clicked.connect(self.input.clear)
        self.shell.currentIndexChanged.connect(self._selection_changed)
        self._update_counter()

    @property
    def busy(self) -> bool:
        return self._thread is not None

    def _action_buttons(self):
        return (self.inspect_button, self.sanitize_button, self.command_button)

    def _update_counter(self):
        self.counter.setText(f"{self.input.byte_count} / {MAX_INPUT_BYTES} bytes UTF-8")

    def _input_changed(self):
        self._revision += 1
        self.output.clear()
        self._update_counter()
        self.status.setText("Entrada modificada; resultado pendiente descartado." if self.busy else "Listo.")

    def _selection_changed(self):
        self.output.clear()
        self._revision += 1
        self.status.setText("Listo.")

    def start(self, operation: str):
        if self.busy or self._closing:
            return
        text = self.input.toPlainText()
        try:
            utf8_size(text)
        except InputError:
            self.output.clear()
            self.status.setText("Error: entrada inválida o superior a 1 MiB UTF-8.")
            return
        self.output.clear()
        self._job += 1
        self._job_revision = self._revision
        try:
            self._launch(text, operation)
        except Exception:
            # No exception messages from Qt, constructors or start() escape
            # through the event loop. Retain any already running worker.
            if self._thread is not None and not self._thread.isRunning():
                self._thread.deleteLater()
                self._thread = None
                self._worker = None
            if not self.busy:
                for button in self._action_buttons():
                    button.setEnabled(True)
                self.shell.setEnabled(True)
            self.status.setText("Error: no se pudo iniciar la operación.")

    def _launch(self, text: str, operation: str):
        self._worker = Worker(self._job, text, operation, self.shell.currentData(), self)
        self._thread = self._worker
        self._worker.completed.connect(self._completed)
        self._worker.failed.connect(self._failed)
        self._thread.finished.connect(self._finished)
        for button in self._action_buttons():
            button.setEnabled(False)
        self.shell.setEnabled(False)
        self.status.setText("Procesando…")
        self._thread.start()

    def _current(self, job: int) -> bool:
        return job == self._job and self._revision == self._job_revision and not self._closing

    @Slot(int, object)
    def _completed(self, job: int, result: Result):
        if not self._current(job):
            return
        # No block/character limit: placeholders can expand the sanitized text.
        try:
            self.output.setPlainText(result.text)
        except Exception:
            self.output.clear()
            self.status.setText("Error: no se pudo presentar el resultado.")
            return
        if result.shown is None:
            self.status.setText(f"Sanitización completa; hallazgos: {result.total}.")
        else:
            self.status.setText(f"Hallazgos: {result.total}; se muestran {result.shown}.")

    @Slot(int, str)
    def _failed(self, job: int, message: str):
        if self._current(job):
            self.output.clear()
            self.status.setText(message)

    @Slot()
    def _finished(self):
        if self._thread is None:
            return
        # finished can precede native thread teardown. Poll without blocking
        # the event loop; retain the Python/Qt object until teardown is done.
        if not self._thread.wait(0):
            QTimer.singleShot(10, self._finished)
            return
        self._thread.deleteLater()
        self._worker = None
        self._thread = None
        if self._closing:
            QTimer.singleShot(0, self.close)
            return
        for button in self._action_buttons():
            button.setEnabled(True)
        self.shell.setEnabled(True)

    def closeEvent(self, event):
        if self.busy:
            self._closing = True
            self.input.setReadOnly(True)
            self.clear_button.setEnabled(False)
            self.output.clear()
            self.status.setText("Esperando a que termine la operación para cerrar…")
            event.ignore()
            return
        self.input.clear()
        self.output.clear()
        event.accept()
