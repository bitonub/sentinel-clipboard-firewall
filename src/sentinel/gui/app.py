"""Deferred Qt entry point; the CLI never imports the graphical interface."""

import sys


def main() -> int:
    try:
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtWidgets import QApplication
        from sentinel.gui.window import Window
    except ImportError:
        print("Error: la GUI requiere el extra opcional; instala sentinel-clipboard-firewall[gui].",
              file=sys.stderr)
        return 2
    except Exception:
        print("Error: no se pudo cargar la interfaz gráfica.", file=sys.stderr)
        return 2
    try:
        # Do not pass application arguments to Qt (or interpret them as input).
        app = QApplication(["sentinel-gui"])
        window = Window()
        window.show()
        code = app.exec()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        return code
    except Exception:
        print("Error: no se pudo iniciar la interfaz gráfica.", file=sys.stderr)
        return 2
