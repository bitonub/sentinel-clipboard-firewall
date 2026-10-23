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
