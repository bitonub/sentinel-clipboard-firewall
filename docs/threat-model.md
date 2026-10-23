# Modelo de amenazas inicial

## Datos que protegemos

- Texto técnico proporcionado por el usuario.
- Credenciales que pueda contener.
- Información de infraestructura.
- Asociaciones entre valores originales y placeholders.

## Límites de confianza

Todo texto recibido se considera entrada no confiable.
Se analiza como datos y nunca como código ejecutable.

La terminal y el sistema operativo están fuera del control
de SENTINEL. Se supone que el equipo no está comprometido.

## Amenazas y controles

| Amenaza | Control | Limitación |
|---|---|---|
| Compartir información sensible accidentalmente | Detección y sanitización | Solo cubre las categorías implementadas |
| Ejecutar comandos recibidos | Análisis estático sin ejecución | El usuario puede ejecutar el comando por su cuenta |
| Filtrar originales mediante diagnósticos | No incluir la entrada en logs ni errores | La terminal puede conservar texto mostrado por el usuario |
| Persistir valores originales | Mapas efímeros por operación | Python no garantiza borrado seguro de memoria |
| Agotar memoria con entradas grandes | Lectura acotada a 1 MiB más un byte para detectar exceso | El límite no sustituye pruebas de rendimiento |
| Alterar texto ajeno al hallazgo | Sustituir únicamente intervalos validados | Los detectores pueden cometer errores |
| Generar falsa confianza | Documentar alcance y limitaciones | Ausencia de hallazgos no significa seguridad |
| Capturar sin límite la salida de wl-paste | Lectura máxima de 1 MiB más un byte, plazo y limpieza acotada | La compatibilidad depende del compositor Wayland |
| Filtrar texto mediante procesos del portapapeles | Argumentos fijos, shell=False, stdin para wl-copy y diagnósticos descartados | wl-copy y el compositor mantienen la selección para servirla |
| Leer memoria Win32 sin límite o con Unicode malformado | GlobalSize, lecturas acotadas, NUL alineado y UTF-16LE incremental estricto; límite UTF-8 | ctypes exige firmas y punteros correctos; requiere comprobación nativa |
| Sobrescribir una copia concurrente en Windows | Reapertura, comparación de secuencia y texto bajo apertura antes de vaciar | No es una transacción con restauración ni protege frente a cambios posteriores |
| Liberar memoria ya transferida a Windows | Suspender la liberación antes de SetClipboardData; restaurarla solo ante fallo confirmado | Un resultado ambiguo puede dejar el bloque sin liberar; no se promete ausencia de modificación |

## Primer incremento: IPv4 privadas

Las direcciones privadas se consideran información de infraestructura,
no credenciales. Su detección tendrá severidad informativa.

Se comprobarán los rangos RFC 1918 explícitamente.
No se clasificarán automáticamente otras direcciones especiales
como privadas.

## Fuera de alcance

- Malware que ya se ejecuta en el equipo.
- Interceptar o bloquear todos los pegados.
- Detectar todos los formatos de secretos.
- Garantizar que un comando es seguro.
- Eliminar datos del historial del shell o del portapapeles.
- Borrar de forma garantizada valores sensibles de la RAM.

La orden clipboard sanitize no elimina el historial que Klipper u otros
gestores hayan conservado. El indicador sensible de wl-copy es una sugerencia,
no una garantía de eliminación. Lectura y escritura no son atómicas frente a
cambios concurrentes; tras un fallo de escritura no se garantiza restauración.
Los procesos externos tienen plazos de lectura/comunicación y una espera
adicional acotada durante la limpieza. No se garantiza que terminen tras kill:
si no se confirma su terminación se deja de esperar y se devuelve un error
sin detalles sensibles. Los errores de cierre se contienen y no ocultan el
error principal de la operación.

En Windows la selección actual puede incluir HTML/RTF además del texto; una
escritura sanitizada vacía todos esos formatos para no conservar originales
alternativos, perdiendo formato enriquecido. Un fallo después de empezar
EmptyClipboard puede dejar la selección vacía o modificada. No se restaura
automáticamente el original ni se libera el HGLOBAL de una publicación exitosa.
Si una interrupción deja incierto el resultado de SetClipboardData, se conserva
el bloque aunque quizá Windows no lo haya adquirido. Se acepta esa posible
asignación sin liberar para evitar liberar memoria ajena. KeyboardInterrupt se
propaga, sin ocultar la cancelación.
Los reintentos de apertura están acotados; una llamada Win32 síncrona puede
esperar a otra aplicación para el renderizado diferido y no tiene timeout
cancelable de SENTINEL. No se garantiza la liberación si falla la propia API
de limpieza. No hay archivos, monitorización ni historial propio.

El historial de Windows, la sincronización entre dispositivos, RDP y gestores
externos pueden conservar o transportar copias fuera del proceso. SENTINEL
no elimina esas copias ni garantiza borrado de RAM. Las pruebas automatizadas
inyectan una API Win32 falsa en Linux y Windows; no consultan el portapapeles
real. Implementado con pruebas simuladas no significa verificado en una sesión
Windows. El procedimiento nativo está en windows-clipboard.md.

## Interfaz gráfica opcional

La entrada y la salida sanitizada son visibles en pantalla; capturas de pantalla
y el entorno de escritorio quedan fuera del control de SENTINEL. Los metadatos
no contienen valores originales. Errores del motor, del inicio de tareas o de
la presentación no reproducen excepciones ni contenido. No se usan formatos
ricos ni apertura de enlaces al presentar texto no confiable.

Se limita el documento aceptado a 1 MiB UTF-8 y se revalida antes del análisis.
Qt puede reservar memoria para un pegado antes de rechazarlo; tampoco se limita
la salida sanitizada a 1 MiB, pues los placeholders pueden expandirla. Mostrar
solo 200 hallazgos limita la presentación, no el trabajo de detección.
Los resultados se asocian a la revisión analizada para evitar presentar una
sanitización obsoleta. El cierre conserva el trabajador hasta su terminación,
sin forzar su destrucción ni bloquear la interfaz. No existe un plazo duro del
motor ni borrado seguro de RAM. Deshacer está desactivado; no hay historial
propio ni persistencia. Qt solo accede al portapapeles por acciones manuales
del usuario. La GUI no utiliza el adaptador Wayland ni elimina historiales de
gestores externos. Las pruebas automatizadas usan offscreen y datos sintéticos;
la revisión visual nativa en Fedora/Wayland se realiza por separado.

## Datos de desarrollo

Todos los ejemplos y casos de prueba serán sintéticos.
No se utilizarán datos internos de empresas ni de clientes.
