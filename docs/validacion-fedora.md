# Validación nativa de Fedora/Wayland — entornos, método y límites

Observaciones del **24 de octubre de 2026**; alcance consolidado el día 25.
Edición pública del 26 de octubre. No se repitió la aceptación nativa por
publicar este informe. Los casos E1/I1, W1-W4 y G1-G7 tienen evidencia dentro
de la configuración descrita; no equivalen a soporte universal de Linux.

```sh
QT_QPA_PLATFORM=wayland QT_DISABLE_EMOJI_SEGMENTER=1 sentinel-gui
```

Ejecutar desde el entorno instalado; las rutas de este documento son ejemplos
neutros. El ajuste de emoji pertenece a la configuración efectivamente observada.

Identidad del producto: commit 6bbff3a3c277748117a5709eca8df159e2737cea.
Antes de la instalación se verificaron SHA-256 del traslado, 59 archivos y el
HEAD de una copia nueva con su documentación local. Una modificación sintética
fue rechazada en la prueba previa del verificador. Una comprobación adicional
de bundle fuera de un repositorio se descartó como error de procedimiento;
clonado/verificación posteriores correctos. Esto identifica la copia, no es
aceptación gráfica. Los módulos del candidato público siguen siendo los mismos.

### Entorno e instalación (E1/I1)

- Fedora Linux 44 KDE Plasma, x86_64; kernel 7.2.8-200.fc44.x86_64.
- Sesión gráfica 2: `Name=<usuario>`, Desktop=KDE, Type=wayland, Active=yes,
  Remote=no. `loginctl show-session self` no identificó al proceso del ejecutor;
  se utilizó la alternativa prevista: listar sesiones y consultar la gráfica.
- XDG_SESSION_TYPE=wayland, XDG_CURRENT_DESKTOP=KDE,
  WAYLAND_DISPLAY=wayland-0. No se simuló Wayland mediante variables.
- CPython 3.14.7, GCC 16.1.1, Linux x86_64.
- wl-clipboard 2.2.1; RPM
  `wl-clipboard-2.2.1^git20251124.e808203-2.fc44.x86_64`.
- Configuración declarada: `org.kde.breezedark.desktop`; tema oscuro observado
  en capturas nativas. KScreen identifica eDP-1, 1920×1080, escala Wayland 1
  (100%). El valor Xwayland Scale=1 no se usa para deducir esta escala.
- Configuración de historial/sincronización no acreditada; no se leyeron datos
  del historial ni se cambiaron preferencias.
- CLI instalada normalmente desde esta copia en `.venv-ci/fedora`, sin Qt;
  GUI instalada normalmente en `.venv/fedora`. Ambos pip check: código 0.
- PySide6, Essentials, Addons y shiboken6: 6.11.2; Qt 6.11.2.
  Metadatos Linux de PySide6: Python >=3.10,<3.15. Se conserva en el proyecto
  `PySide6>=6.11.2,<6.12`.
- Los 24 módulos instalados de cada entorno coinciden por SHA-256 con el
  manifiesto de transferencia. Importaciones desde site-packages de cada
  entorno, sin usar otra copia. E1 e I1 aprobados dentro de estos límites.
- pip construyó ruedas temporales como parte de la instalación normal; no se
  preparó una distribución final ni se repitieron gates de paquetes/suites.

### Incidente inicial de W1 — registro histórico

Se crearon las tres muestras sintéticas conocidas en `.venv/manual-fedora/`,
UTF-8/LF, sin acceso previo al portapapeles. Tras aviso explícito de reemplazo
sin restauración, `wl-copy --sensitive` publicó `original.txt`: código 0.
Un lector independiente, acotado a 1 MiB+1 y timeout de seis segundos, confirmó
bytes exactamente iguales al original; lector y comparación terminaron con 0.
No se imprimió ni persistió lo leído del portapapeles.

Tras un segundo aviso se ejecutó desde `/ruta/local` la CLI instalada:
`sentinel clipboard sanitize`. Terminó con código 0 y
`Sin cambios; hallazgos: 0.`; se esperaban seis hallazgos y publicación de la
salida sanitizada. **W1 no aprobado.** No se realizó otra lectura ni una nueva
publicación, y no se ejecutaron W2-W4 ni la GUI después de la discrepancia.
No está determinada la causa: posible cambio externo entre comparación y
operación, o fallo por aislar; el código 0 no basta para aprobar el caso.
No se atribuye un error de producto sin reproducción mínima.

### Investigación ordenada y resultados nativos posteriores

1. Se verificó el shebang de `.venv-ci/fedora/bin/sentinel`: utiliza el Python
   de ese entorno. `sys.executable`, `sys.prefix`, entry point y las rutas de
   `sentinel.cli`, dispatcher y adaptador Wayland corresponden a sus
   site-packages. Versión 0.0.1; direct_url apunta a esta copia restaurada.
2. Sin portapapeles, `sentinel scan` sobre `original.txt` devolvió seis
   hallazgos, código 0. `sentinel sanitize` produjo exactamente `esperado.txt`;
   el motor instalado también devolvió seis y salida idéntica.
3. Tras aviso se publicó el original y se confirmó con lector independiente.
   Sin cambiar de ejecución del terminal, CLI: `Portapapeles actualizado;
   hallazgos: 6.`, código 0, stderr vacío; lectura posterior exacta al esperado.
4. Al iniciar W2 desde otra ejecución, la comparación dejó de coincidir y se
   detuvo el caso antes de ejecutar W3. Una clasificación posterior solo contra
   original/esperado/público/vacío dio falso en los cuatro; no se mostró, guardó
   ni analizó el contenido desconocido. No quedaba servidor wl-copy activo.
   El usuario confirmó que no había copiado nada ni conocía una app automática.
5. Para aislar el ciclo de vida del ejecutor, se creó el auxiliar manual local
   `.venv/manual-fedora/protocolo_interactivo.py`, fuera de la suite y runtime.
   Cada caso se invocó explícitamente en una terminal persistente (PID 11498),
   con avisos y comparaciones previas. Repetir W1 estaba justificado por la
   invalidación de W2 entre sesiones; no se repitieron gates históricos.

Resultados de esa terminal persistente:

| Caso | Evidencia | Resultado |
|---|---|---|
| W1 | Productor 0; original exacto; CLI seis hallazgos, 0 y stderr vacío; salida UTF-8/LF exacta, repeticiones/Unicode incluidos | Aprobado |
| W2 | Tras terminar SENTINEL, otra invocación manual del lector y pausa adicional de 3 s: esperado exacto; servidor wl-copy PID 11546 seguía activo | Aprobado |
| W3 | Esperado exacto antes/después; `Sin cambios; hallazgos: 0.`, código 0, stderr vacío | Aprobado |
| W4 | Publicación pública, código 0 y bytes exactos; CLI Sin cambios/cero hallazgos, 0 y stderr vacío; bytes iguales después | Aprobado |

El proceso que servía W4 era wl-copy PID 11613, con grupo y sesión 11498,
los mismos del auxiliar de terminal; no era el proceso SENTINEL, que ya había
terminado. Tras salir explícitamente del auxiliar (código 0), PID 11613 dejó de
existir y otra lectura ya no coincidía con ninguna muestra ni vacío.
No se usaron --clear/--watch/--primary ni se borró historial.

**Causa y límite de la investigación:** se reprodujo la pérdida de la selección
sintética al cerrar la sesión del ejecutor junto con su servidor wl-copy; con
la sesión persistente, el servidor y la selección sobrevivieron a SENTINEL.
La evidencia apunta al ciclo de vida del ejecutor y gestión externa de la
selección, no a un fallo reproducible del motor/instalación/adaptador. No se
identificó qué componente publicó la selección posterior. Tampoco puede
reconstruirse qué texto leyó la primera CLI con cero hallazgos, pues no se
registró; no se afirma que aquel contenido fuera la salida sanitizada. W3 sí
acredita que cero hallazgos es correcto sobre la salida sanitizada conocida.
No se corrigió producto ni se añadieron regresiones/reinstalaciones sin motivo.

La GUI instalada se lanzó con QT_QPA_PLATFORM=wayland para iniciar G1-G7.
El operador confirmó el bloque guiado para el primer bloque guiado: muestra
breve con sanitización esperada, Tab/Shift+Tab y activación con Espacio (G1),
selección y rechazo de X/Retroceso en Salida (G2), descarte de Salida al editar
Entrada y ambas áreas vacías al usar Limpiar tras volver a sanitizar (G4).
Se aprueban G1/G2/G4 por confirmación contextual, no por el proceso abierto.
Los casos restantes se completaron después mediante control nativo, según
el registro siguiente. No se ejecutó QtTest/offscreen en esta ronda.

### Control nativo posterior: G3/G5/G6/G7

Se utilizaron AT-SPI para las
acciones de la GUI instalada y del editor, KWin para activar/redimensionar y
solicitar cierre, y Spectacle para capturar únicamente las ventanas objetivo.
AT-SPI IsEnabled estaba en false: se activó temporalmente y se devolvió a
false al terminar, comprobado por D-Bus. ScreenReaderEnabled no se modificó.
No se añadieron dependencias al proyecto, no se parchearon site-packages y no
se simuló Wayland ni se convirtió un proceso abierto en evidencia visual.

- **G3:** salida completa sintética coincidente con esperado.txt en la GUI;
  copia nativa, comparación independiente acotada, pegado por Edit → Paste en
  un documento nuevo de KWrite y lectura del documento exactamente iguales.
  Selección/copia nativa desde KWrite y pegado de vuelta en Entrada: texto
  exacto, Unicode y LF preservados. Se inspeccionaron capturas de KWrite y
  de SENTINEL. La transferencia se repitió en la configuración compatible
  después del diagnóstico de dibujo descrito abajo; no hubo texto desconocido.
- **G5:** tema oscuro, eDP-1 1920×1080, escala 100%; ventana maximizada con
  frame de 1920×1006 y reducida a 687×480, respetando el mínimo de ancho
  declarado (687; alto mínimo 350). Texto, controles y selector completos,
  accesibles y legibles en las capturas compatibles. Una geometría forzada de
  640 de ancho, inferior al mínimo, se descartó como evidencia del tamaño
  soportado; la captura conservada respeta 687. Otros temas/escalas/monitores
  no probados. El emoji se ve monocromo con el ajuste, sin pérdida de texto.
- **G6:** cierre por la operación normal del gestor de ventanas, equivalente
  a la X, sin señal de terminación ni kill. GUI inicial PID 11720: código 0.
  GUI compatible PID 13821: código 0, proceso ausente al finalizar, stdout
  vacío; stderr contiene cinco avisos estáticos de AT-SPI y nada más.
- **G7:** lanzador portable de transferencia, GUI PID 14136, backend Wayland,
  ajuste de emoji y demora sintética explícita de cinco segundos. Se observó
  por accesibilidad el estado Procesando, se solicitó cierre normal durante
  ese estado y se observó Esperando a que termine la operación para cerrar.
  La captura nativa muestra la espera y controles deshabilitados. Terminó
  a los **5,163 s** desde Sanitizar, código 0, proceso ausente. Stdout declara
  la demora de cinco segundos; stderr contiene tres avisos estáticos AT-SPI.
  No acredita rendimiento bajo carga real ni ausencia universal de bloqueos.

Los avisos de stderr son:
`qt.accessibility.atspi: AtSpiAdaptor::applicationInterface does not implement
"GetApplicationBusAddress" "/org/a11y/atspi/accessible/root"`.
No se ocultaron ni se presentaron como stderr vacío. Las operaciones utilizadas
funcionaron pese a ellos; no se acredita toda la API de accesibilidad.

Incidencias del controlador, fuera del producto: PasteText de accesibilidad en
KWrite devolvió true sin insertar; la primera activación aislada de Paste
tampoco bastó. Abrir Edit y activar Paste produjo el documento correcto y
verificable. La inyección de Tab por AT-SPI no dio cambio de foco observable:
no se usó para aprobar G1, que conserva confirmación humana. Una primera
consulta de Procesando fue demasiado temprana/con caché y no solicitó cierre
ni aprobó G7; se repitió el observador con caché desactivada y espera acotada
hasta observar el estado real. Un primer auxiliar KWin usó una firma D-Bus
incorrecta: se corrigió solo el auxiliar. Los scripts KWin se descargaron tras
cada operación; no se instalaron como preferencias persistentes.

### Dibujo del emoji: límite y configuración compatible

Sin ajuste, el texto y sus bytes son correctos y el emoji aparece en KWrite,
pero no se dibuja en Entrada/Salida de la GUI con PySide6/Qt 6.11.2. Se aisló
fuera de SENTINEL en una operación mínima de dibujo de Qt: el texto ASCII/α
se dibuja, el emoji con selección de fuente de color no pinta píxeles; la
misma operación con `QT_DISABLE_EMOJI_SEGMENTER=1` sí dibuja el emoji.
Este diagnóstico de QImage no es aceptación de GUI ni reemplaza las capturas
Wayland: después se repitieron los casos visuales afectados en la ventana real.
No se determinó una causa binaria más precisa dentro de Qt/fuentes.

La variable está documentada por [Qt: Emoji in Qt 6.9](https://www.qt.io/blog/emoji-in-qt-6.9).
Se aplicó solo al proceso de validación, sin modificar el entorno global,
fuentes del sistema, código del producto, paquetes instalados o rango Qt.
Comando reproducible de la configuración GUI propuesta:

```bash
QT_QPA_PLATFORM=wayland QT_DISABLE_EMOJI_SEGMENTER=1 \
  /ruta/al/proyecto/.venv/fedora/bin/sentinel-gui
```

**Límite de la configuración:** el arranque sin la variable mantiene el
problema visual observado; no se corrigió por código ni se garantizan color,
combinaciones ZWJ u otros conjuntos de emoji. G3/G5 acreditan la configuración
con ajuste, no el arranque predeterminado sin él.

### Matriz técnica consolidada

| ID | Resultado actual |
|---|---|
| E1 | Aprobado: Fedora/KDE/Wayland, versiones, tema y escala identificados |
| I1 | Aprobado: restauración, HEAD, 59 archivos e instalaciones verificadas |
| W1-W4 | Aprobados nativamente, con terminal persistente |
| G1/G2/G4 | Aprobados por confirmación humana del primer bloque |
| G3 | Aprobado: transferencia nativa exacta SENTINEL/KWrite/SENTINEL; observación visual con el ajuste |
| G5 | Aprobado en tema oscuro/100%, maximizada y 687×480, con el ajuste |
| G6 | Aprobado: cierre normal nativo, código 0; avisos AT-SPI explícitos |
| G7 | Aprobado: Procesando → espera → salida 0; demora instrumentada de cinco segundos |

Los resultados se limitan a esta configuración compatible. No se extrapolan
al arranque sin ajuste, otros Python/Qt, temas, escalas o ausencia de gestor
externo de selección. El contenido inicial de W1 no fue registrado y no puede
reconstruirse; no se afirma que fuera ya sanitizado.

## Evidencia anterior y distinción de métodos

Se conserva como antecedente una suite Fedora/Python 3.14 offscreen de 165
pruebas, incluidas 33 GUI, sin omisiones; compileall y diff --check correctos.
La corrección histórica de Qt también registró gates con CPython 3.11.17 y
3.14.7, 127 pruebas y 33 GUI, Qt 6.11.2. Los primeros registros de construcción
usaron Qt 6.12.0: no autorizan reinstalar esa serie excluida. El CI histórico
39906129598 corresponde a 6bbff3a y no identifica una nueva sesión Fedora.
Estos antecedentes no acreditan portapapeles real ni interacción visual;
la aceptación nativa se obtuvo después con los métodos de este informe.

## Evidencia local y limpieza de la sesión

Se conservaron resultados y capturas solo de ventanas con datos sintéticos;
los registros detallados y auxiliares permanecen fuera del paquete. Las GUI
y KWrite de prueba terminaron; se descartaron únicamente buffers sintéticos.
Accesibilidad IsEnabled, activada temporalmente, se devolvió a false; no se
cambió ScreenReaderEnabled. No se restauró selección ni se borró historial.
Los resúmenes de este documento conservan resultados aunque se eliminen los
entornos de prueba. La identidad histórica de esos auxiliares no los convierte
en funciones o archivos distribuidos de SENTINEL.

## Identificar la configuración real, sin leer la selección

```bash
cat /etc/fedora-release
uname -m
printf 'XDG_SESSION_TYPE=%s\nXDG_CURRENT_DESKTOP=%s\nWAYLAND_DISPLAY=%s\n' "$XDG_SESSION_TYPE" "$XDG_CURRENT_DESKTOP" "$WAYLAND_DISPLAY"
loginctl show-session self --property=Type --property=Desktop --property=Remote
python3 --version
command -v python3.14 python3.11 wl-copy wl-paste
rpm -q wl-clipboard
wl-copy --version
wl-paste --version
```

La sesión debe ser realmente Wayland; no basta establecer una variable para
simularla. Si loginctl no identifica la sesión del terminal, registrar esa
limitación y consultar la sesión gráfica activa sin inventar escritorio.
Registrar tema/escala disponibles, monitor si se conoce y si hay gestor de
historial/sincronización; si se desconocen, anotarlo sin modificar configuraciones.
No volcar todas las variables de entorno, credenciales o contenido del clipboard.

## Entornos Linux e identidad de lo instalado

Elegir un Python disponible compatible, preferentemente 3.14 o 3.11, y anotar
su revisión exacta. El PySide6 6.11.2 instalado en Windows declara Python
`>=3.10,<3.15`; no usar Python 3.15 por defecto ni quitar el límite Qt para
resolver una incompatibilidad. Confirmar los metadatos reales de la instalación
Linux. No se exige repetir dos rondas Fedora si una configuración cumple el alcance.

Ejemplo si existe python3.14, desde la copia restaurada:

```bash
python3.14 -m venv .venv-ci/fedora
python3.14 -m venv .venv/fedora
.venv-ci/fedora/bin/python -m pip install .
.venv/fedora/bin/python -m pip install '.[gui]'
.venv-ci/fedora/bin/python -m pip check
.venv/fedora/bin/python -m pip check
.venv/fedora/bin/python -c 'import sys,struct,sentinel; from importlib.metadata import version; from PySide6.QtCore import qVersion; print(sys.version); print(struct.calcsize("P")*8); print(sentinel.__file__); print(version("PySide6")); print(qVersion())'
SENTINEL_WORK="$PWD"
SENTINEL_CLI="$SENTINEL_WORK/.venv-ci/fedora/bin/sentinel"
SENTINEL_PY="$SENTINEL_WORK/.venv-ci/fedora/bin/python"
SENTINEL_GUI="$SENTINEL_WORK/.venv/fedora/bin/sentinel-gui"
```

Adaptar el nombre del intérprete si se elige 3.11. Verificar que CLI no tiene
Qt y que la importación instalada corresponde al entorno, no a otro proyecto.
No activar ni trasladar venv de Windows. No repetir las suites o gates de
paquetes aprobados: pip check de entornos Linux nuevos y comprobaciones de
identidad no equivalen a revalidar Windows ni a construir distribución final.

## Protocolo manual Wayland utilizado

Estas órdenes documentan el procedimiento de escritorio Fedora. No forman una suite
automatizada: el operador invoca cada caso, observa y registra antes de seguir.
Usar solo la selección ordinaria, sin --primary, --watch, --clear o borrado de
historial. Antes de cada escritura hay un aviso. No se respalda ni restaura la
selección anterior y --sensitive es solo una sugerencia al gestor.

### Preparación sintética, sin acceder al portapapeles

Desde la copia de trabajo crear `.venv/manual-fedora/` y estos archivos UTF-8
con LF y salto final. Son datos públicos de prueba:

```text
# original.txt (excluir esta línea descriptiva)
α 😀 password=SyntheticFedora42 pwd=SyntheticFedora42
host=10.20.30.40 public=8.8.8.8
Authorization: Bearer SyntheticBearer42
postgres://SyntheticUser42:SyntheticPass42@db.example/app
```

```text
# esperado.txt (excluir esta línea descriptiva)
α 😀 password=[PASSWORD_1] pwd=[PASSWORD_1]
host=[PRIVATE_IP_1] public=8.8.8.8
Authorization: Bearer [BEARER_TOKEN_1]
postgres://[POSTGRES_USER_1]:[POSTGRES_PASSWORD_1]@db.example/app
```

```text
# publico.txt (excluir esta línea descriptiva)
public=8.8.8.8
status=synthetic
```

Guardar los tres literales anteriores en .venv/manual-fedora como UTF-8/LF,
sin las líneas descriptivas, sin leer una selección ajena ni ejecutar datos.

Lector independiente para comparar sin imprimir o guardar lo leído, usando
una variable que apunte al archivo sintético esperado:

```bash
set -o pipefail
timeout 6s wl-paste --no-newline --type text | "$SENTINEL_PY" -c 'import sys; from pathlib import Path; expected=Path(sys.argv[1]).read_bytes(); actual=sys.stdin.buffer.read(1048577); ok=actual==expected; print("coincidencia_exacta="+str(ok)); raise SystemExit(0 if ok else 2)' "$SENTINEL_EXPECTED"
SENTINEL_COMPARE_EXIT=$?
printf 'comparacion_exit=%s\n' "$SENTINEL_COMPARE_EXIT"
```

Leer como máximo 1 MiB más un byte y aplicar timeout no garantiza que otra
aplicación no cambie la selección. Si no coincide o el pipeline falla, detener
el caso; no mostrar el texto ni ejecutar SENTINEL sobre una copia desconocida.

### W1: sanitización completa

```bash
printf '%s\n' 'AVISO: la publicación sintética reemplazará el portapapeles actual; no se restaurará.'
wl-copy --type 'text/plain;charset=utf-8' --sensitive < "$SENTINEL_WORK/.venv/manual-fedora/original.txt"
SENTINEL_PRODUCER_EXIT=$?
printf 'productor_exit=%s\n' "$SENTINEL_PRODUCER_EXIT"
SENTINEL_EXPECTED="$SENTINEL_WORK/.venv/manual-fedora/original.txt"
```

Comprobar productor_exit=0 y ejecutar el lector independiente: debe coincidir
exactamente. Solo entonces:

```bash
printf '%s\n' 'AVISO: SENTINEL sustituirá la muestra conocida y sus formatos; no se restaurará el contenido anterior.'
cd "$HOME"
"$SENTINEL_CLI" clipboard sanitize
SENTINEL_OPERATION_EXIT=$?
printf 'sentinel_exit=%s\n' "$SENTINEL_OPERATION_EXIT"
SENTINEL_EXPECTED="$SENTINEL_WORK/.venv/manual-fedora/esperado.txt"
```

Esperar código 0 y solo `Portapapeles actualizado; hallazgos: 6.`; verificar
con el lector la salida completa, repeticiones, Unicode y saltos exactos.

### W2 y W3: disponibilidad tras salir e idempotencia

Después de volver al prompt de W1, ejecutar el lector otra vez tras una breve
pausa: acredita disponibilidad después de terminar SENTINEL, no ausencia de
procesos wl-copy/compositor que sirven la selección. Sin copiar de nuevo:

```bash
printf '%s\n' 'AVISO: operación explícita sobre la salida sintética conocida; podría reemplazar la selección si cambió.'
"$SENTINEL_CLI" clipboard sanitize
SENTINEL_OPERATION_EXIT=$?
printf 'sentinel_exit=%s\n' "$SENTINEL_OPERATION_EXIT"
```

Esperar `Sin cambios; hallazgos: 0.`, código 0, y lector exacto con esperado.txt.
La lectura compara bytes, no demuestra por sí sola inexistencia de reescritura.

### W4: texto público

```bash
printf '%s\n' 'AVISO: publicar texto público sintético reemplazará el portapapeles actual; no se restaurará.'
wl-copy --type 'text/plain;charset=utf-8' --sensitive < "$SENTINEL_WORK/.venv/manual-fedora/publico.txt"
SENTINEL_PRODUCER_EXIT=$?
printf 'productor_exit=%s\n' "$SENTINEL_PRODUCER_EXIT"
SENTINEL_EXPECTED="$SENTINEL_WORK/.venv/manual-fedora/publico.txt"
```

Verificar productor y bytes antes de operar. Después:

```bash
printf '%s\n' 'AVISO: operación explícita sobre texto público conocido; se espera no modificarlo.'
"$SENTINEL_CLI" clipboard sanitize
SENTINEL_OPERATION_EXIT=$?
printf 'sentinel_exit=%s\n' "$SENTINEL_OPERATION_EXIT"
```

Esperar Sin cambios, cero hallazgos y código 0; verificar bytes con el lector.
Registrar observaciones/códigos en la matriz, sin copiar contenido desconocido.

## Protocolo GUI en una configuración real

Abrir la GUI instalada con backend nativo Wayland, sin offscreen:

```bash
QT_QPA_PLATFORM=wayland QT_DISABLE_EMOJI_SEGMENTER=1 "$SENTINEL_GUI"
SENTINEL_GUI_EXIT=$?
printf 'gui_exit=%s\n' "$SENTINEL_GUI_EXIT"
```

Para G1/G2 escribir en Entrada `password=SyntheticFedora42 host=10.20.30.40`;
la activación de Sanitizar debe producir
`password=[PASSWORD_1] host=[PRIVATE_IP_1]`. Para copia/pegado con Unicode y
saltos puede escribirse la muestra completa conocida. No usar datos ajenos.
No ejecutar todavía el cierre de la ventana hasta completar los casos:

- G1: con una operación ya terminada, Tab recorre Inspeccionar → Sanitizar →
  Analizar comando → selector → Limpiar → Entrada → Salida → inicio; Shift+Tab
  invierte el orden. Espacio activa Sanitizar con el foco allí.
- G2: seleccionar Salida con Ctrl+A; intentar X/Retroceso no cambia el texto.
- G3: **avisar antes de Ctrl+C**, porque reemplaza la selección. Copiar solo
  la salida sintética a un documento nuevo de un editor disponible y pegar
  de vuelta en Entrada. Observar texto plano, Unicode y saltos si se usa la
  muestra completa; no exigir un editor que no esté instalado.
- G4: editar Entrada descarta Salida; Limpiar vacía ambas áreas. No repetir
  otras categorías o reglas como una nueva aceptación general ya confirmada.
- G5: observar maximizada y reducida, foco/controles, barras si hacen falta.
  Registrar el tema/escala disponible y sus límites; no exigir otros monitores
  ni cambiar configuraciones ajenas al alcance para registrar el caso.
- G6: cerrar normalmente con la X, registrar observación, código y stderr seguro.
- G7: si la operación termina demasiado rápido, usar el lanzador manual de
  abajo. Impone backend Wayland y una demora sintética de cinco segundos
  antes del análisis instalado. Escribir la muestra breve, pulsar Sanitizar
  y cerrar mientras Procesando. Observar la espera y el cierre al terminar,
  sin error/bloqueo. Registrar código, demora y carácter instrumentado, sin
  atribuir rendimiento bajo carga real.

Ejemplo de lanzador solo para ese protocolo, fuera del código instalado:

```python
import os
import sys
import time
if sys.platform != 'linux' or os.environ.get('XDG_SESSION_TYPE') != 'wayland':
    raise SystemExit('Usar en la sesión gráfica Wayland identificada.')
os.environ['QT_QPA_PLATFORM'] = 'wayland'
os.environ['QT_DISABLE_EMOJI_SEGMENTER'] = '1'
from sentinel.gui import worker
from sentinel.gui.app import main
original_analyze = worker.analyze

def delayed_analyze(text, operation, shell):
    time.sleep(5)
    return original_analyze(text, operation, shell)

worker.analyze = delayed_analyze
if __name__ == '__main__':
    raise SystemExit(main())
```

El lanzador no modifica site-packages ni inyecta entradas; la observación es
humana o de una herramienta de control realmente disponible, no una inferencia
por proceso abierto. Si no hay confirmación de algún caso, permanece pendiente.

## Ante fallos y criterios de evidencia

Aislar entorno y reproducción mínima antes de cambiar código. No relajar el
rango Qt, ocultar errores/importaciones ni modificar precauciones Win32.
Tras una corrección de producto, añadir una regresión útil y verificar solo
los entornos afectados. Los tests usan dobles y QtTest offscreen; el protocolo
real permanece manual. Una observación ausente no se convierte en aprobación.

Referencias: [wl-clipboard](https://github.com/bugaevc/wl-clipboard/blob/master/data/wl-clipboard.1)
y [loginctl](https://www.freedesktop.org/software/systemd/man/latest/loginctl.html).
