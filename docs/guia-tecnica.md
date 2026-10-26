# Guía técnica para explicar SENTINEL

Basada en el código **0.0.1**. Edición pública del 26 de octubre de 2026.
Código propio bajo MIT; paquetes y condiciones en [packaging.md](packaging.md).

SENTINEL inspecciona texto proporcionado explícitamente y sustituye ciertos
valores sensibles por etiquetas. También analiza comandos como datos, sin
ejecutarlos. No intercepta todos los pegados ni detecta cualquier secreto.

## Arquitectura y recorrido de un ejemplo

Hay tres entradas: stdin por CLI, selección explícita mediante adaptador de
portapapeles y editores de la GUI. Todas reutilizan el núcleo y sus detectores.
El núcleo trabaja con cadenas; no abre archivos, red, procesos ni portapapeles.

Ejemplo sintético, con salto final:

```text
α 😀 password=Synthetic42 pwd=Synthetic42
host=10.20.30.40 public=8.8.8.8
Authorization: Bearer SyntheticBearer42
postgres://SyntheticUser42:SyntheticPass42@db.example/app
```

1. Para `sentinel sanitize`, [cli.main()](../src/sentinel/cli.py) lee hasta
   1 MiB + 1 byte, rechaza exceso y decodifica UTF-8 estrictamente.
2. [sanitize()](../src/sentinel/core/sanitize.py) llama a
   [scan()](../src/sentinel/core/scan.py), que reúne y resuelve los intervalos
   de los cuatro detectores. Aquí quedan **seis hallazgos**: dos contraseñas,
   una IPv4 privada, un Bearer y usuario/contraseña PostgreSQL.
3. El sanitizador reemplaza esos intervalos y conserva el resto. La CLI emite
   bytes UTF-8 a stdout; `scan`, en cambio, devolvería metadatos JSON.

```text
α 😀 password=[PASSWORD_1] pwd=[PASSWORD_1]
host=[PRIVATE_IP_1] public=8.8.8.8
Authorization: Bearer [BEARER_TOKEN_1]
postgres://[POSTGRES_USER_1]:[POSTGRES_PASSWORD_1]@db.example/app
```

Seis hallazgos no significan seis etiquetas distintas: la contraseña repetida
comparte etiqueta. `8.8.8.8` queda igual porque no pertenece a RFC 1918.
El ejemplo y su segunda sanitización se comprobaron sin portapapeles.

## Mapa de archivos y funciones

| Archivo | Responsabilidad y puntos para leer |
|---|---|
| [cli.py](../src/sentinel/cli.py) | `main()`: argumentos, stdin, validación y presentación; `clipboard sanitize` no lee stdin. |
| [findings.py](../src/sentinel/core/findings.py) y [scan.py](../src/sentinel/core/scan.py) | `Finding`: regla, categoría, posiciones, severidad y explicación, sin valor original. `scan()`: combina y resuelve intervalos. |
| Detectores: [private_ipv4.py](../src/sentinel/detectors/private_ipv4.py), [password.py](../src/sentinel/detectors/password.py), [bearer.py](../src/sentinel/detectors/bearer.py), [postgres.py](../src/sentinel/detectors/postgres.py) | `scan()` en cada uno; PostgreSQL añade `analyze()`, que devuelve hallazgos y tramos de URLs con credenciales. IPv4 valida con `ipaddress` y rangos explícitos. |
| [sanitize.py](../src/sentinel/core/sanitize.py) y [limits.py](../src/sentinel/limits.py) | `sanitize()` construye texto y etiquetas; `utf8_size()` valida el presupuesto por bloques. `scan()`/`sanitize()` por sí solos no imponen el límite de las interfaces. |
| [command_guard.py](../src/sentinel/core/command_guard.py) y [powershell_guard.py](../src/sentinel/core/powershell_guard.py) | `check_command()` selecciona Bash o delega en `check_powershell()`: heurísticas de descarga por pipe a intérprete/Invoke-Expression. |
| [adapters/clipboard.py](../src/sentinel/adapters/clipboard.py) | `sanitize_clipboard()`: carga diferida según `sys.platform`; contratos `ClipboardResult` y `ClipboardError`. |
| [windows.py](../src/sentinel/adapters/windows.py) y [wayland.py](../src/sentinel/adapters/wayland.py) | `sanitize_clipboard()` en ambos; Windows usa `Win32API` y `_read_text()`; Wayland, `_read_clipboard()`, `_write_clipboard()` y limpieza acotada. |
| [gui/app.py](../src/sentinel/gui/app.py) y [editor.py](../src/sentinel/gui/editor.py) | `main()` importa Qt al abrir la GUI; `InputEditor` valida ediciones y pegados. |
| [gui/window.py](../src/sentinel/gui/window.py) y [worker.py](../src/sentinel/gui/worker.py) | `Window.start()`, `_current()`, `_finished()`, `closeEvent()`; `Worker.run()` ejecuta `analyze()` y emite resultados sin modificar widgets. |

## Windows y Wayland: mismo motor, distinta integración

| Aspecto | Windows | Wayland |
|---|---|---|
| Acceso/codificación | `ctypes`, DLL del sistema y CF_UNICODETEXT; UTF-16LE incremental y NUL alineado, presupuesto contado en UTF-8. | Procesos wl-paste/wl-copy del paquete externo wl-clipboard; UTF-8 estricto y lectura acotada. |
| Antes de publicar | Prepara memoria; reabre y compara secuencia y texto bajo apertura antes de vaciar. | Lee y después escribe; no tiene esa comprobación de conflicto ni atomicidad entre ambas operaciones. |
| Publicación | EmptyClipboard elimina formatos previos; SetClipboardData transfiere la propiedad de memoria. No se libera un bloque adquirido por Windows. | Argumentos fijos, shell=False y datos por stdin; texto plano con --sensitive, que es una sugerencia al gestor. |
| Esperas | Reintentos de apertura hasta 5 s; no es un timeout global de las llamadas Win32. | Lectura/comunicación hasta 5 s y espera de limpieza hasta 2 s adicionales por proceso; no garantiza terminación. |

Ambos evitan escribir si el texto no cambia y no prometen restauración tras un
fallo de publicación. La GUI utiliza copia/pegado manual de Qt, **no estos
adaptadores**. Los casos Wayland aprobados usaron terminal persistente para
mantener wl-copy tras salir SENTINEL. El contenido inicial discrepante de W1
no está reconstruido: no se debe inventar qué contenía.

## Etiquetas, solapamientos e idempotencia

En `sanitize()`, la clave del mapa efímero es **(rule_id, valor)**, no la
categoría ni un identificador global. Dos reglas pueden compartir categoría
sin compartir etiqueta. Los contadores se reinician en cada operación y son
independientes por prefijo. Se reservan las etiquetas preexistentes de
credenciales que enumera su expresión regular; PRIVATE_IP no está en esa
reserva explícita. Las etiquetas no cifran ni permiten recuperar el original.

Los intervalos de `Finding` son posiciones de caracteres Python `[start, end)`,
no offsets UTF-8. `scan()` suprime genéricos que empiezan dentro de URLs con
credenciales, amplía coberturas necesarias y combina intersecciones para no
perder sufijos. Por ejemplo:

```text
password=prefix/postgres://user:synthetic,tail@db.example/app
→ password=[PASSWORD_1]
```

No basta con sustituir solo la contraseña PostgreSQL si queda parte del valor
exterior sensible. Las reglas reconocen/omiten sus placeholders y el ejemplo
cumple `sanitize(sanitize(text)) == sanitize(text)`: **idempotencia**, no
reversibilidad. Casos relacionados están en [test_password.py](../tests/test_password.py)
y [test_postgres.py](../tests/test_postgres.py), sin ejecutarlos de nuevo aquí.

## Privacidad, alcance y estado de implementación

Implementado: cuatro detectores, sanitización, Command Guard Bash/PowerShell,
CLI, GUI opcional y ambos adaptadores. Los detectores tienen gramáticas y
rangos concretos: no cubren todos los secretos ni todas las direcciones
especiales. Command Guard no interpreta programas completos ni garantiza
seguridad. La entrada y salida sanitizada pueden conservar datos no detectados.

Los hallazgos/errores no incluyen originales, pero entrada y salida son
visibles en GUI; los literales escritos en órdenes pueden quedar en el
historial del shell. No hay red durante el análisis, historial propio ni
persistencia de mapas; eso no impide capturas,
swap, gestores externos o copias de otras aplicaciones. Python no garantiza
borrado seguro de RAM. El límite es de **entrada**, no de salida ni de toda la
memoria que Qt pueda reservar al pegar. Véase [threat-model.md](threat-model.md).

La GUI limita a 200 los hallazgos presentados, no el análisis; conserva la
sanitización completa y Qt normaliza finales de línea. Fedora está aceptado
con `QT_QPA_PLATFORM=wayland QT_DISABLE_EMOJI_SEGMENTER=1`, en las versiones y
condiciones de [validacion-fedora.md](validacion-fedora.md). No extender esa
aceptación a otro entorno ni usar offscreen como evidencia nativa.

No implementados ni prometidos para este cierre: instalador con runtime,
monitorización automática y más familias de detectores. Serían ampliaciones
con alcance propio. La entrega acordada sigue siendo wheel/sdist 0.0.1;
la licencia propia es [MIT](../LICENSE), sin relicenciar las dependencias.
La verificación de archivos se explica en [validacion-paquetes.md](validacion-paquetes.md).

## Tres decisiones técnicas y sus razones

1. **Núcleo sin I/O y Qt opcional:** permite reutilizar reglas desde CLI/GUI y
   probarlas sin selección real; la CLI base conserva dependencias externas
   vacías. Ver core, adaptadores y [pyproject.toml](../pyproject.toml).
2. **Sustituir intervalos con etiquetas por operación:** conserva estructura,
   coherencia de repeticiones y cobertura de solapamientos sin persistir mapas.
   Ver `scan()` y `sanitize()`; el coste es que puede ocultarse una candidata
   completa ante ambigüedad y no se ofrece recuperación del valor.
3. **Trabajador y revisiones de entrada en GUI:** `Worker.run()` evita analizar
   en el hilo de widgets; `Window._current()` descarta resultados obsoletos y
   `_finished()` coordina un cierre sin destruir un hilo activo. No elimina el
   GIL ni ofrece cancelación inmediata o plazo duro del análisis.

## Preguntas de comprensión

1. ¿Qué cambia entre `scan` y `sanitize` para el mismo texto?
2. ¿Por qué el ejemplo tiene seis hallazgos pero cinco etiquetas distintas?
3. ¿En qué unidades se miden posiciones y presupuesto de entrada?
4. ¿Por qué no se sustituye `8.8.8.8`?
5. ¿Qué riesgo evita cubrir una contraseña que contiene una URL PostgreSQL?
6. ¿La misma contraseña conserva etiqueta entre ejecuciones diferentes?
7. ¿Qué significa idempotencia y qué no garantiza?
8. ¿Qué protección de concurrencia tiene Windows que falta en Wayland?
9. ¿Qué ocurre si editas Entrada mientras trabaja la GUI?
10. ¿Qué dirías ante «sin hallazgos significa seguro» y «ya hay instalador»?

## Respuestas — consulta después de intentar explicarlas

1. `scan` devuelve metadatos sin valores; `sanitize` devuelve el texto con
   sustituciones, conservando lo no cubierto.
2. Las dos apariciones de Synthetic42 usan PASSWORD_1 en la misma regla.
3. Posiciones: caracteres Python. Presupuesto de las interfaces: bytes UTF-8,
   máximo 1 MiB; la lectura del byte adicional detecta exceso.
4. Solo se sustituyen IPv4 válidas de los tres rangos RFC 1918 definidos.
5. Evita dejar visible un sufijo sensible al reemplazar solo un tramo interior.
6. No hay correspondencia global persistente; el mapa y los contadores son
   locales. Una coincidencia de etiqueta entre ejecuciones no prueba identidad.
7. Volver a sanitizar una salida cubierta no la cambia; no implica que sea
   segura, completa ni reversible.
8. Recomprueba secuencia y texto bajo apertura antes de EmptyClipboard;
   Wayland no hace esa comprobación y su lectura/escritura no son atómicas.
9. Se limpia Salida y cambia la revisión; el resultado del trabajo viejo se
   descarta. El hilo no se cancela forzosamente.
10. Cero hallazgos solo significa que estas reglas no encontraron candidatos.
    No hay instalador: la entrega sigue siendo wheel/sdist 0.0.1, con licencia
    MIT propia y licencias separadas para dependencias.
