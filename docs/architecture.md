# Arquitectura inicial

## Flujo de datos

stdin → CLI → motor → resultado

clipboard sanitize → adaptador Wayland → motor → adaptador Wayland → estado

sentinel-gui → editor acotado → QThread → motor → señales → salida de texto plano

La CLI recibe texto UTF-8 y limita la entrada a 1 MiB.
El núcleo recibe texto y devuelve resultados sin acceder
a la terminal, al portapapeles, al disco ni a la red.

## Componentes

- CLI: interpreta opciones, valida la entrada y presenta resultados.
- Adaptador Wayland: solo ante clipboard sanitize, lee una selección textual
  mediante wl-paste con lectura acotada y plazo total, valida UTF-8 y transmite
  el resultado a wl-copy por stdin si hay cambios. Los procesos usan argumentos
  fijos, shell=False, 5 segundos de lectura/comunicación y hasta 2 segundos
  adicionales de espera de limpieza. Usa Popen sin gestores de contexto que
  introduzcan esperas implícitas; todas las esperas de terminación tienen plazo.
  Pipes sin búfer y selectores se cierran con errores protegidos. La limpieza
  no oculta errores principales ni garantiza que todo proceso pueda terminar.
  stdout/stderr externos no se muestran.
  No guarda contenido en archivos. La CLI solo muestra estado y recuento.
- Detector: identifica valores y sus posiciones en el texto.
- Sanitizador: sustituye los intervalos detectados.
- Command Guard: tokeniza comandos como datos y devuelve metadatos de riesgo
  y sugerencias sin conservar el comando en los hallazgos. La CLI selecciona
  explícitamente Bash (predeterminado) o PowerShell. `CF-BASH-001` busca
  descargas entregadas por pipe directo a Bash o sh; `CF-PS-001` busca descargas
  canalizadas directamente a Invoke-Expression. Los analizadores son estáticos
  e independientes, sin ejecución ni expansión de variables.

## Primer detector

Se localizarán candidatos IPv4 y se validarán con ipaddress,
de la biblioteca estándar de Python.

Solo se clasificarán como privadas las direcciones incluidas
en los tres rangos RFC 1918 definidos en spec.md.
No se utilizará is_private como único criterio.

## Hallazgos

Cada hallazgo incluirá:

- identificador de regla;
- categoría;
- posición inicial y final, en caracteres;
- severidad;
- explicación.

Los intervalos usarán la convención de Python: inicio incluido
y final excluido. No guardarán una copia adicional del valor original.

## Sanitización

El sanitizador conservará el texto fuera de los intervalos detectados.
Asignará placeholders según el orden de aparición.
Una misma IPv4 recibirá el mismo placeholder en una operación.

El mapa de sustituciones será local a cada operación.
No se devolverá ni guardará en archivos.

## Salida de terminal

stdout contendrá el resultado solicitado.
stderr contendrá diagnósticos y errores sin reproducir la entrada.

## Interfaces

El adaptador Wayland reutiliza el núcleo sin introducir subprocess en él.
La GUI opcional reutiliza scan, sanitize y check_command directamente. Qt solo
se importa al iniciar sentinel-gui; la CLI y el núcleo no dependen de él.
La constante de 1 MiB se comparte desde sentinel.limits. El editor valida bytes
UTF-8, con comprobaciones adicionales antes y dentro del trabajador.

El trabajador es un QThread que implementa únicamente run; no modifica widgets.
Devuelve texto sanitizado completo o los metadatos de hasta 200 hallazgos con
el total. Las excepciones se convierten en diagnósticos estáticos. Solo hay una
operación simultánea. Una revisión de entrada identifica resultados obsoletos,
que no se presentan; editar elimina también los resultados ya visibles.
La ventana coordina el cierre con finished y comprueba wait(0) mediante el
bucle de eventos antes de liberar el hilo; no espera de forma bloqueante.
La finalización no tiene un plazo duro ni cancelación forzada. El mapa de
sustituciones permanece local al motor. La GUI no usa el adaptador Wayland,
archivos de contenido, QSettings ni acceso automático al portapapeles.
