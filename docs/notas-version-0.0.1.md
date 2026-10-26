# SENTINEL Clipboard Firewall 0.0.1 — primera entrega

**Candidato de publicación; todavía no publicado.**
Herramienta local de revisión explícita de texto y comandos. Distribución
wheel/sdist, Python instalado por separado y GUI opcional.

## Qué ofrece

- Inspección y sanitización local de texto entregado explícitamente: IPv4
  privadas RFC 1918, asignaciones password/passwd/pwd, encabezados Bearer y
  credenciales en URLs PostgreSQL, según las gramáticas implementadas.
- Etiquetas coherentes para repeticiones dentro de una operación y resolución
  de solapamientos para evitar sustituciones parciales. Metadatos sin valores
  originales; el texto no cubierto por las reglas se conserva.
- Command Guard heurístico para descargas por pipe directo a Bash/sh o
  Invoke-Expression en PowerShell. Analiza los comandos como datos: no los ejecuta.
- CLI sin dependencias externas Python, GUI Qt opcional con entrada de texto
  plano/salida de solo lectura, teclado, limpieza y cierre coordinado.
- Sanitización de portapapeles solo por una orden explícita: adaptador Win32
  en Windows y wl-clipboard en Wayland. No hay monitorización automática.

## Instalación y alcance observado

Entrega mediante wheel y sdist 0.0.1. Hace falta Python; no es un .exe,
AppImage ni instalador autónomo y no incluye un runtime. Instalar el wheel
con python -m pip en un entorno virtual; añadir el extra [gui] para GUI.
PySide6 se mantiene en >=6.11.2,<6.12 y se instala por separado. El README
incluye órdenes específicas de Fedora Bash y Windows PowerShell.

- **Windows:** Windows 11 x64, CPython 3.11.9 y 3.14.9, PySide6/Qt 6.11.2;
  interacción GUI y portapapeles dentro del alcance de sus informes. Tema
  oscuro y 144 DPI; otros temas/escalas no se dan por comprobados.
- **Fedora:** Fedora 44 KDE/Wayland x86_64, CPython 3.14.7, wl-clipboard 2.2.1,
  PySide6/Qt 6.11.2, oscuro/100%, eDP-1 1920×1080. La GUI se aceptó con:

```sh
QT_QPA_PLATFORM=wayland QT_DISABLE_EMOJI_SEGMENTER=1 sentinel-gui
```

El ajuste permitió dibujar el emoji de la muestra, monocromo; sin él queda
el límite visual de esa instalación. No se garantizan otros emoji/ZWJ o
entornos. Los casos Wayland usaron una terminal persistente para conservar
wl-copy después de salir SENTINEL. El contenido inicial discrepante de W1 no
se registró y no está reconstruido; los casos posteriores se verificaron con
muestras conocidas. Cierres con trabajador activo se coordinaron con una
demora sintética explícita de cinco segundos, no una carga real equivalente.

## Límites y uso responsable

SENTINEL no es protección universal ni certifica que un texto o comando sea
seguro. Solo cubre reglas concretas; puede omitir secretos o producir falsos
positivos. El presupuesto de entrada es 1 MiB UTF-8; no es un límite universal
de memoria ni de salida. El editor Qt normaliza finales de línea.

Antes de usar clipboard sanitize o copiar desde GUI, advierte que se puede
reemplazar la selección. No hay restauración garantizada ni borrado de
historial/sincronización externos o de RAM. Wayland no ofrece una operación
atómica de lectura/escritura; --sensitive es una sugerencia. La GUI no consulta
ni transforma automáticamente la selección. Offscreen y CI no sustituyen
aceptaciones nativas, y la etiqueta py3-none-any no certifica toda plataforma.

## Licencia y verificación

Código/documentación propios bajo MIT, Copyright (c) 2026 bitonub. Qt/PySide6
y demás dependencias conservan sus licencias; consultar LICENSE y
THIRD_PARTY_NOTICES.md. No se declara cumplimiento global de una redistribución
de Qt que no forma parte de estos paquetes. Donaciones opcionales, sin enlace
inventado ni condición de donación para usar el programa.

El candidato público se verifica con inventarios explícitos, archivos MIT y
avisos, instalación externa, smokes CLI/GUI offscreen, pip check y reconstrucción
completa desde sdist. Los resultados y hashes propios figuran en VALIDACION.md y
SHA256SUMS.txt, adjuntos al candidato. No se reejecutan las comprobaciones
nativas por esta revisión de documentación. El CI histórico no se presenta
como una nueva ejecución de este candidato.

## Archivos de distribución

- sentinel_clipboard_firewall-0.0.1-py3-none-any.whl
- sentinel_clipboard_firewall-0.0.1.tar.gz
- SHA256SUMS.txt
- VALIDACION.md

Este candidato público conserva los mismos módulos de producto y cambia el
contenido documental y las exclusiones. No comparte necesariamente hashes con
construcciones anteriores de 0.0.1. No incluye documentos de coordinación,
respaldos privados, logs o exportaciones de conversaciones. Los archivos
incorrectamente identificados solo por versión o los archivos automáticos de
código fuente de una plataforma no sustituyen al sdist comprobado por su hash.
