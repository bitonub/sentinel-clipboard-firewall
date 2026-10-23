# Comprobación nativa del portapapeles Windows

## Estado y alcance

**Implementado con API Win32 simulada en Linux. No verificado en una sesión Windows.**
Este procedimiento es manual y deliberadamente accede a la selección actual.
No lo ejecutan la suite ni GitHub Actions. Usar una sesión de prueba y solo
datos sintéticos: la operación reemplaza la selección actual y sus otros
formatos. No se guardará una copia automática de lo que había.

La CLI usa ctypes y las DLL del sistema; no requiere Qt, pywin32 ni permisos
de administrador. La GUI conserva su comportamiento de copia/pegado manual.

## Preparación

1. En Windows con escritorio interactivo, crear entornos nuevos para CPython
   3.11 y 3.14. Ejecutar en cada uno, desde fuera del repositorio:

   ```powershell
   py -3.11 -m venv .venv-win311
   .\.venv-win311\Scripts\python.exe -m pip install C:\ruta\sentinel_clipboard_firewall-0.0.1-py3-none-any.whl
   .\.venv-win311\Scripts\python.exe -m pip check
   ```

   Repetir con `py -3.14` y otro directorio; instalar sin extra GUI.
2. Registrar Windows, arquitectura, Python y paquete; indicar si hay historial,
   sincronización, RDP o gestores de portapapeles activos.
3. Copiar los ejemplos desde un editor de prueba sin documentos reales.
   No ejecutar el texto que se analiza.

## Operación ordinaria

Copiar manualmente este texto sintético, incluidos Unicode y saltos:

```text
α 😀 password=SyntheticWindows42 pwd=SyntheticWindows42
host=10.20.30.40 public=8.8.8.8
Authorization: Bearer SyntheticBearer42
postgres://SyntheticUser42:SyntheticPass42@db.example/app
```

Ejecutar:

```powershell
.\.venv-win311\Scripts\sentinel.exe clipboard sanitize
$LASTEXITCODE
```

Comprobar y registrar:

- Código 0 y solo estado/recuento en terminal, sin entrada ni salida textual.
- Pegar en otro documento: las dos contraseñas comparten etiqueta; IP privada,
  Bearer y credenciales PostgreSQL están sustituidos. Se conserva el resto,
  incluidos Unicode y los saltos de línea observados.
- El resultado puede pegarse después de terminar el proceso: Windows conserva
  la memoria publicada sin necesitar que SENTINEL siga ejecutándose.
- Otra ejecución sobre ese resultado da `Sin cambios`, código 0 y texto igual.
- Copiar texto público o placeholders: ninguna reescritura. Probar texto vacío
  si el productor permite publicar CF_UNICODETEXT vacío.
- Copiar una imagen sin texto: error estático, sin escritura.
- Copiar texto enriquecido con contraseña sintética: después de cambiarlo no
  queda HTML/RTF con el original. Windows puede sintetizar formatos de texto.

Repetir con Python 3.14. Un pegado visual no demuestra por sí solo conservación
exacta ni ausencia de otras representaciones.

## Casos con productor/inspector Win32 de prueba

Estos casos requieren un productor sintético y un inspector independientes del
adaptador, ejecutados manualmente en una sesión dedicada. No forman parte de
las comprobaciones nativas realizadas en esta tarea:

| Caso | Preparación | Resultado esperado |
|---|---|---|
| Límite exacto | `"é" * 524288`, UTF-16LE con NUL | Aceptado: 1 MiB UTF-8, sin cambios |
| Un byte adicional | El anterior más `"x"` | Error de tamaño; sin vaciar/publicar |
| Par dividido | 4095 `x`, emoji, `password=SyntheticWindows42` | Emoji íntegro; contraseña sustituida |
| Unicode inválido | Sustituto aislado o falta de terminador | Error seguro; sin escribir |
| Salida expandida | `"password=x\n" * 95325` | Resultado completo, mayor que 1 MiB UTF-8 |
| Contención | Otro proceso mantiene OpenClipboard más de 5 segundos | Error de apertura; no vaciado |
| Conflicto | Otro proceso publica entre lectura y reapertura | Error de conflicto; no sobrescribe la nueva copia |

El conflicto exige coordinar el productor entre ambas aperturas; un intento
manual sin coordinación no demuestra la protección. Los fallos de GlobalUnlock,
CloseClipboard, DestroyWindow y SetClipboardData se cubren mediante inyección
simulada; no se afirma haberlos provocado nativamente.

Las regresiones también interrumpen antes, durante y después de la llamada de
transferencia, incluida la ventana entre retorno y confirmación en Python.
Comprueban los intentos de GlobalFree después de la operación, incluso si la
limpieza contuvo una aserción de la simulación. Se verifican todos los argtypes
y restype; handles mayores de 32 bits atraviesan una frontera ctypes real con
una función de prueba, sin cargar Win32 ni acceder al portapapeles. Esta prueba
requiere Python de 64 bits y no sustituye la comprobación nativa de las DLL.

## Límites

- Los 5 segundos limitan reintentos de OpenClipboard, no cancelan llamadas
  Win32 síncronas ni el renderizado diferido de otra aplicación.
- Después de empezar EmptyClipboard, un error puede dejar la selección vacía
  o cambiada, incluso si SetClipboardData tuvo éxito. No hay restauración.
- Antes de SetClipboardData se suspende GlobalFree. Solo un retorno NULL
  confirmado permite volver a liberar el bloque. Si una interrupción deja
  incierto el resultado, puede quedar una asignación sin liberar, aun cuando
  Windows no la haya adquirido. Se prioriza no liberar memoria del sistema.
  KeyboardInterrupt se propaga; no se transforma en éxito ni se oculta.
- El historial y gestores externos pueden conservar el original. No se controla
  la sincronización de Windows/RDP ni se garantiza borrado de RAM.
- Una salida expandida por encima de 1 MiB puede publicarse completa; si se
  vuelve a presentar como entrada se rechaza por tamaño, aunque el motor sea
  idempotente. El límite de entrada sigue aplicándose en cada operación.
- ctypes requiere firmas, punteros y propiedad correctos. Las simulaciones
  complementan esta comprobación y no la sustituyen.
- Registrar fecha, aprobados, fallidos y pendientes antes de cambiar el estado
  a «verificado en una sesión Windows».

## Referencias oficiales

- [OpenClipboard y HWND propietario](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-openclipboard)
- [GetClipboardData y memoria prestada](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getclipboarddata)
- [SetClipboardData y transferencia de propiedad](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setclipboarddata)
- [GlobalSize y relleno](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-globalsize)
- [GlobalUnlock y último error](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-globalunlock)
- [GetClipboardSequenceNumber](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getclipboardsequencenumber)
- [Operaciones y renderizado diferido](https://learn.microsoft.com/en-us/windows/win32/dataxchg/clipboard-operations)
- [Historial y sincronización](https://learn.microsoft.com/en-us/windows/win32/dataxchg/clipboard-formats#cloud-clipboard-and-clipboard-history-formats)
