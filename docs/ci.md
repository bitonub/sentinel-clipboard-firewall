# CI con GitHub Actions

El workflow `.github/workflows/ci.yml` se ejecuta en push, pull_request y
workflow_dispatch. Usa entornos virtuales nuevos por trabajo, sin paquetes del
usuario ni instalaciones editables. Python 3.11 es la versión mínima declarada;
se prueba la última revisión disponible de esa familia y Python 3.14.

## Trabajos y gates

| Trabajo | Matriz | Gates |
|---|---|---|
| CLI | Ubuntu 24.04 / Windows 2025 × Python 3.11 / 3.14 | Qt debe estar ausente; suite completa con exactamente las omisiones de GuiTests; pip check, compileall y diff --check |
| GUI | Ubuntu 24.04 / Windows 2025 × Python 3.11 / 3.14 | Extra GUI instalado; suite completa con cero omisiones y descubrimiento no vacío de GuiTests; pip check, compileall y diff --check |
| Paquetes | Ubuntu 24.04 / Windows 2025, Python 3.14 | Wheel y sdist, inventario y metadatos, instalación limpia sin Qt fuera del repositorio, reconstrucción desde sdist y repetición de los smoke tests |
| Auditoría | Ubuntu 24.04, Python 3.14 | Resolución de runtime base y GUI en entorno separado, auditoría de dependencias transitivas fijadas a las versiones resueltas y pip check |

`tools/run_tests.py` comprueba las identidades de las pruebas omitidas, no solo
su cantidad. En CLI solo se acepta omitir la clase GuiTests cuando Qt falta.
Cualquier omisión ajena, fallo, error, ausencia de descubrimiento GUI o ejecución
incompleta falla el trabajo. En GUI ninguna omisión está permitida. El resumen
indica cuántas pruebas se descubrieron, cuántas son GUI y las omisiones esperadas
y reales. No se usa continue-on-error. Las matrices no cancelan sus otras
combinaciones ante el primer fallo.

Qt usa exclusivamente la plataforma virtual offscreen en las pruebas. En Linux
se instalan las bibliotecas EGL/OpenGL/xkbcommon necesarias. PYTHONUTF8 y
PYTHONIOENCODING fijan UTF-8 en los procesos que respetan esas variables.
Los smoke tests del wheel y el inventario JSON de dependencias usan
`python -I -X utf8`: conservan el aislamiento y fuerzan UTF-8 explícitamente,
sin depender de esas variables, que `-I` ignora. El inventario también se
decodifica explícitamente como UTF-8 en el proceso padre.
Las pruebas de portapapeles usan procesos simulados; la copia GUI solo usa el
portapapeles virtual de offscreen, sin consultar el del escritorio.

`tools/check_packages.py` exige inventarios explícitos del wheel y del sdist,
compara los módulos con el código fuente y comprueba los puntos de entrada,
Requires-Python y que PySide6 solo pertenezca al extra gui. Crea otro entorno
temporal sin Qt ni herramientas de construcción, instala el wheel, cambia a
un directorio externo y ejecuta scan, sanitize y ambos analizadores. El smoke
test carga los puntos de entrada instalados mediante Python, compatible con
los lanzadores GUI sin consola de Windows. Comprueba también el diagnóstico
sin Qt. Un audit hook rechaza eventos socket de Python durante estos análisis.
Se reconstruye un wheel del sdist extraído, se comparan archivos y contenidos
y se repiten instalación, smoke tests y pip check.

## Auditoría de dependencias

`requirements-dev.txt` contiene únicamente herramientas de desarrollo. No se
añaden a las dependencias runtime de pyproject.toml ni al wheel. El sdist incluye
esas instrucciones y los scripts de CI para poder repetir sus comprobaciones.

`tools/audit_runtime.py` instala el wheel con `[gui]` en un entorno nuevo y lee
sus metadatos. Recorre el grafo desde SENTINEL para el runtime base y para el
extra gui, respetando marcadores y extras transitivos. Solo se auditan las
dependencias externas alcanzables; pip, build y pip-audit no se incluyen salvo
que realmente llegaran a ser dependencias runtime. SENTINEL, como paquete local
no publicado, no se consulta como dependencia externa.

El runtime CLI actual está vacío y se informa explícitamente. La GUI debe
incluir PySide6. La auditoría usa pip-audit con --strict, --no-deps y
--disable-pip sobre las versiones ya resueltas. No ignora vulnerabilidades ni
aplica correcciones automáticas: un código distinto de cero, error de resolución
o fallo de consulta falla el gate. Instalar paquetes y consultar los avisos
requiere red; los motores de texto de SENTINEL siguen sin usarla.

Esta auditoría detecta avisos conocidos por el servicio PyPI para esas versiones
de paquetes. No certifica bibliotecas del sistema ni todos los componentes
nativos embebidos en Qt. No inspecciona texto del usuario. Las versiones se
resuelven de nuevo en cada ejecución: no es un lock reproducible. El grafo
auditado corresponde a Linux/Python 3.14; otras combinaciones podrían resolver
dependencias diferentes y requieren auditoría adicional si se distribuyen.

## Seguridad y acciones fijadas

- Permiso global exclusivo: `contents: read`; los demás permisos quedan sin conceder.
- Sin secretos ni credenciales configuradas, publicación, releases o escritura
  en el repositorio. Checkout no persiste las credenciales de lectura implícitas
  de GitHub. No se usa pull_request_target ni runners propios.
- Las expresiones del workflow solo seleccionan valores de matrices estáticas;
  no se interpola texto de PR, ramas o issues en órdenes de shell.
- Acciones fijadas a commits completos, con versión comentada. Se verificaron
  el 22 de octubre de 2026 mediante la API pública de los repositorios oficiales:

| Acción | Etiqueta | SHA verificado |
|---|---|---|
| [actions/checkout](https://github.com/actions/checkout/tree/v7.0.1) | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| [actions/setup-python](https://github.com/actions/setup-python/tree/v7.1.0) | v7.1.0 | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` |

Ambas acciones usan Node 24 en esos commits. Al actualizar una acción, verificar
la etiqueta y su commit de nuevo en el repositorio oficial, revisar sus cambios
y modificar juntos SHA y comentario. Los runners hospedados y los paquetes de
desarrollo/sistema no están fijados a una imagen o cierre de dependencias exacto.

## Repetir gates localmente

En un entorno limpio sin Qt, instalar `pip install .` y ejecutar:

```sh
python tools/run_tests.py --mode cli
python -m pip check
```

En otro entorno con `pip install '.[gui]'`:

```sh
python tools/run_tests.py --mode gui
python -m pip check
```

En un entorno de desarrollo separado:

```sh
python -m pip install -r requirements-dev.txt
python -m build
python tools/check_packages.py
python tools/audit_runtime.py
python -m compileall -q src tests tools
git diff --check
```

Utilizar un directorio dist sin artefactos de otras versiones; el gate exige un
solo wheel y un solo sdist. Los scripts seleccionan automáticamente bin o
Scripts/python.exe para los entornos temporales. Las dependencias de desarrollo
y los avisos de seguridad se descargan solo en los pasos que los necesitan.

## Límites y estado

### Comprobaciones locales realizadas

En Fedora 44, CPython 3.14.7, el 22 de octubre de 2026:

- actionlint 1.7.12 validó el workflow. El binario se obtuvo del repositorio
  oficial y se verificó contra el checksum publicado con su release.
- Gate GUI: 124 pruebas ejecutadas, incluidas 32 GUI, sin omisiones ni fallos.
- Gate CLI en `.venv-ci` nuevo sin Qt: 124 pruebas descubiertas, 92 ejecutadas
  y exactamente 32 omisiones esperadas de GuiTests; sin fallos.
- Gate de paquetes: wheel de 27 archivos y sdist de 56, instalación externa,
  reconstrucción y smoke tests correctos con sockets Python bloqueados.
- pip-audit 2.10.1: grafo CLI vacío; seis dependencias externas de GUI auditadas,
  sin vulnerabilidades conocidas reportadas por PyPI en esa consulta.
  Se resolvieron PySide6, Essentials, Addons y shiboken6 6.12.0, y Pdf/WebEngine
  6.12.0.140. Esto no certifica la ausencia de vulnerabilidades en Qt nativo.
- pip check en entornos de desarrollo y CLI, compileall y diff --check correctos.

Estas comprobaciones iniciales no incluyeron Python 3.11 ni Windows.

### Diagnóstico de la ejecución 39898145390

Se revisaron `gh run view 39898145390 --log-failed`, el listado de trabajos
y los registros completos de los tres trabajos GUI fallidos. GUI Ubuntu/Python
3.14 pasó; los fallos se agrupan en dos causas:

- Producto, salida CLI en Windows: `test_bearer_scan_and_sanitize` falla en
  la comparación de bytes en los cuatro trabajos Windows, CLI y GUI con ambos
  Python. GitHub enmascara los operandos como `Authorization: ***`. La reproducción
  local con un TextIOWrapper configurado como Windows confirma la conversión
  LF a CRLF (y CRLF a CRCRLF). `sanitize` ahora escribe bytes UTF-8 por stdout,
  conservando acentos y los finales de línea originales. No se relaja la prueba.
- Dependencia GUI/Python 3.11 en Linux: tras `Ran 125 tests ... OK`, el proceso
  aborta con `Fatal Python error: bool_dealloc: deallocating True or False: bug
  likely caused by a refcount error in a C extension`, estado `finalizing` y
  código 134. Se reprodujo localmente con CPython 3.11.17 y PySide6 6.12.0,
  primero con el gate GUI y después solo con `tests.test_gui`.

La reproducción mínima del segundo fallo no importa SENTINEL ni crea widgets:

```python
from PySide6.QtCore import QObject, Signal

class Sender(QObject):
    changed = Signal()

sender = Sender()
for _ in range(1000):
    sender.changed.emit()
```

Con Python 3.11/PySide6 6.12.0 cada emisión pierde una referencia a `True`;
la repetición causa SIGABRT, el mismo diagnóstico `bool_dealloc` y código 134
en shell (-6 al observarlo mediante subprocess). Con Qt/Shiboken 6.11.2 la
reproducción termina con código 0 y sin cambio en el contador de referencias.
Esto identifica una incompatibilidad de la dependencia; no un error de las
aserciones ni ausencia de bibliotecas del runner. Qt se importó e inicializó
y las 32 pruebas GUI originales se ejecutaron sin omisiones.

El extra GUI se acota temporalmente a `PySide6>=6.11.2,<6.12`. La regresión
ejecuta las emisiones en otro proceso y exige código 0, incluida la finalización
del intérprete. En Python 3.11 exige además referencias estables; desde Python
3.12 `True` es inmortal y su contador no representa su ciclo de vida.
No se usan os._exit ni omisiones para
evitar el aborto. Antes de ampliar el rango de Qt hay que repetir esta prueba
y la matriz completa. Se mantienen Python 3.11/3.14, Linux/Windows y todos
los gates. Una nueva ejecución de los cambios en GitHub y Windows sigue pendiente.

Después de aislar el fallo y corregir el rango, los gates GUI locales finalizaron
con código 0 en Fedora con CPython 3.11.17 y 3.14.7: 127 pruebas, incluidas
33 GUI, sin fallos ni omisiones en cada ejecución. La regresión de finales de
línea usa una salida de texto configurada como Windows; no sustituye una
ejecución nativa de Windows. Para migrar desde Qt 6.12 se recomienda un entorno
virtual nuevo, evitando componentes Pdf/WebEngine antiguos que pip puede retener.
Los gates CLI sin Qt también terminaron con código 0 en ambos Python: 127
descubiertas, 94 ejecutadas efectivamente y 33 omisiones GUI esperadas. Pasaron
la construcción e instalación externa de paquetes, reconstrucción desde sdist,
pip check, compileall, actionlint y git diff --check. La auditoría del nuevo
grafo GUI (cuatro dependencias externas, todas 6.11.2) no reportó avisos conocidos
en la consulta PyPI; mantiene las limitaciones de auditoría descritas arriba.

### Actualización: ejecución real comprobada el 23 de octubre de 2026

Se consultaron los trabajos y registros de
[39906129598](https://github.com/bitonub/sentinel-clipboard-firewall/actions/runs/39906129598),
correspondiente a `6bbff3a3c277748117a5709eca8df159e2737cea`. Sus 11 trabajos
terminaron correctamente: cuatro CLI, cuatro GUI, dos de paquetes y la auditoría.
La matriz incluye Ubuntu 24.04 y Windows 2025 con Python 3.11 y 3.14.

- Cada trabajo GUI: 165 pruebas ejecutadas, incluidas 33 GUI, cero omisiones.
- Cada trabajo CLI sin Qt: 165 descubiertas, 132 ejecutadas efectivamente y
  exactamente 33 omisiones GUI esperadas; ningún fallo.
- Paquetes en ambos sistemas: wheel de 29 archivos y sdist de 61, instalación
  externa, smoke tests y reconstrucción correctos para ese commit.
- Auditoría: sin vulnerabilidades conocidas reportadas en esa consulta;
  mantiene los límites de alcance y fecha descritos anteriormente.

Los párrafos anteriores sobre GitHub pendiente describen el estado histórico
de las correcciones. Esta ejecución posterior verifica esos cambios en CI.
No acredita documentos o cambios locales posteriores al commit indicado ni
una sesión de escritorio nativa. Los resultados e inventarios deberán volver
a comprobarse al modificar el producto o el contenido de sus distribuciones.

### Aceptaciones nativas posteriores y administración del repositorio

La matriz indicada arriba ya pasó en GitHub; debe repetirse tras cambios.
No se configura la protección de ramas desde esta tarea; el administrador
deberá elegir los checks requeridos tras observar sus nombres reales.

Una ejecución Windows de CI no verifica el portapapeles de Windows ni la GUI
nativa. Tampoco offscreen verifica Wayland, X11, temas, HiDPI, accesibilidad o
integración con el compositor. La aceptación nativa Fedora/Wayland posterior
está documentada en [validacion-fedora.md](validacion-fedora.md), dentro de su
configuración: Qt 6.11.2, GUI con QT_DISABLE_EMOJI_SEGMENTER=1 y terminal
persistente en los casos Wayland. La aceptación posterior de GUI Windows en
ambos Python se registra
en [validacion-windows.md](validacion-windows.md), con alcance oscuro/144 DPI
y límites explícitos, separada de los casos de portapapeles y de estos trabajos CI.
Las pruebas del adaptador Windows inyectan una API falsa y memoria sintética,
también al ejecutarse en Windows; sus imports no cargan DLL de portapapeles.
Las pruebas Wayland fijan su backend incluso en Windows para impedir un acceso
nativo accidental. El protocolo manual está en
[windows-clipboard.md](windows-clipboard.md): además de la simulación, registra
casos nativos en Windows 11/Python 3.11.9 y 3.14.9, con límites explícitos.
Esa evidencia local posterior no forma parte de los trabajos de GitHub descritos.
El audit hook de sockets es un control de regresión de Python, no un aislamiento
de red a nivel de sistema operativo ni un sandbox para código no confiable.

Referencias: [seguridad de GitHub Actions](https://docs.github.com/en/actions/reference/security/secure-use)
y [pip-audit](https://github.com/pypa/pip-audit).

## Documentación pública de la versión 0.0.1

Los resultados CI citados corresponden al commit histórico indicado y no a
una ejecución del candidato público. Las comprobaciones locales de paquetes
se documentan en VALIDACION.md, adjunto a ese candidato. Los informes nativos
mantienen sus entornos y límites; no se repiten por cambios documentales.
