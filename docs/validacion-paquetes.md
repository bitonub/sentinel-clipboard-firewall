# Verificación de paquetes 0.0.1 — método y antecedentes

Edición pública del 26 de octubre de 2026. No incluye rutas personales ni
registros de coordinación. Los datos de la sección histórica describen la
construcción anterior a las exclusiones públicas, no los adjuntos de este
candidato. Los informes originales se conservan en un respaldo privado.

## Alcance y licencia

Versión 0.0.1; wheel y sdist, sin instalador ni runtime embebido. El usuario
eligió MIT para el código propio, con **Copyright (c) 2026 bitonub**. LICENSE
contiene el texto estándar; pyproject.toml declara license="MIT" y license-files
con LICENSE y THIRD_PARTY_NOTICES.md, compatibles con setuptools>=77.

Ambos artefactos incluyen licencia y avisos, comprobados byte por byte contra
los fuentes. Wheel: dist-info/licenses; sdist: raíz. License-Expression=MIT y
los dos License-File se verifican en METADATA y ambos PKG-INFO. Las dependencias conservan sus propios avisos y licencias.

El aviso de terceros delimita el contenido propio y los paquetes externos.
Se inspeccionaron metadatos y hashes de los cuatro wheels Linux 6.11.2 usados
para la instalación GUI. PySide6/Qt y sus componentes mantienen sus licencias;
no se incluyen sus binarios/textos/código en nuestros wheel/sdist salvo las
referencias de nuestro aviso. No se declara cumplimiento global de las
condiciones de una redistribución de Qt, Python o wl-clipboard no realizada.

## Fuente, herramientas e inventarios

- HEAD de producto: 6bbff3a3c277748117a5709eca8df159e2737cea; src/sentinel
  sin cambios frente a ese producto.
- Fedora 44 x86_64; CPython **3.14.7**, GCC 16.1.1.
- Frontend **build 1.6.1**; backend aislado **setuptools 84.2.1**;
  **packaging 26.3**, **pyproject_hooks 1.3.3**, pip **26.0.1**.
- SOURCE_DATE_EPOCH=1792994400 (26-10-2026, 00:00 America/Monterrey), usado
  para esta construcción y reconstrucción. No garantiza reproducibilidad
  binaria universal con otras herramientas/fechas/plataformas.
- Inventario del antecedente anterior a la edición pública: **wheel 31 archivos** (24 módulos, cinco metadatos y dos
  archivos de licencia/avisos), **sdist 71 archivos regulares**. Los recuentos
  se observaron con el gate; no se forzaron los inventarios históricos.
- Exclusiones confirmadas por allowlist exacta: entornos, .git, .env, cachés,
  bytecode, capturas, auxiliares/logs de aceptación y artefactos anteriores.
  Esto no equivale a garantizar detección de todo secreto arbitrario en texto.

## Comprobaciones y resultados

| Comprobación | Resultado |
|---|---|
| Regresiones de paquetes y gate de CI afectado | **17 pruebas aprobadas**, ocho nuevas de frontera de paquetes; no suite completa |
| Construcción aislada sdist → wheel | Código 0; backend y avisos de inclusión registrados |
| Inventarios, duplicados, tipos/rutas, CRC, hashes y tamaños RECORD | Correctos; sin archivos ajenos |
| Licencia, avisos, identidad, Python>=3.11, puntos de entrada y extra GUI | Correctos; CLI sin dependencias externas, PySide6>=6.11.2,<6.12 solo para gui |
| Contenido README y todos los fuentes/documentos del sdist | Coinciden exactamente con el snapshot |
| Wheel instalado en entorno CLI limpio externo | Site-packages, no editable, sin Qt/build; pip check correcto |
| Smokes CLI y GUI sin extra | scan, sanitize, Bash/PowerShell correctos; falta de Qt: código 2 seguro, sin traceback; sin sockets Python durante análisis |
| Reconstrucción desde sdist extraído en carpeta nueva | Mismo inventario y contenidos de todos los archivos del wheel; reinstalación y smokes CLI correctos |
| Wheel con extra GUI en otro entorno externo limpio | pip check correcto; PySide6/Essentials/Addons/shiboken6 y Qt **6.11.2** |
| Punto de entrada instalado GUI, offscreen | Texto sintético Unicode sanitizado, archivos MIT instalados y cierre código 0; sin llamadas al portapapeles real |
| pip check de herramientas y git diff --check | Correctos |

Las ocho regresiones cubren aceptación válida y rechazo de licencia ausente,
aviso alterado aun con RECORD consistente, documento sdist cambiado sin alterar
longitud, expresión de licencia errónea, archivo .env sintético no permitido,
miembro wheel duplicado y hash RECORD incorrecto. No se retiran controles del
gate; se añaden verificación de licencia/contenido/RECORD y recuentos reales.

El smoke GUI presenta el aviso estático de offscreen
`This plugin does not support propagateSizeHints()`; no se oculta ni se afirma
stderr vacío. No es aceptación nativa. No se repitieron Windows, Fedora,
portapapeles real, suite completa ni auditoría remota de vulnerabilidades.
El análisis no ejecutó los comandos remotos de muestra.

## Candidato público: contenido y verificación

La edición pública mantiene versión 0.0.1, MIT y los mismos módulos de
src/sentinel. Cambia la documentación incluida y excluye expresamente los tres
registros internos; MANIFEST.in y PUBLIC_DOCUMENTS del gate enumeran los
archivos permitidos. No se incorporan nuevas funciones ni instalador.
Los recuentos se obtienen de los archivos construidos, sin fijar los históricos.

Las verificaciones afectadas se ejecutan sobre una carpeta nueva: inventarios,
licencia, metadatos, contenidos, hashes RECORD, instalación externa, smokes,
pip check y reconstrucción desde sdist con comparación completa del wheel.
Se añade regresión para rechazar registros internos y documentos no permitidos.
No se repiten aceptaciones nativas ni la suite completa por este cambio.

Los cuatro adjuntos públicos propuestos son wheel, sdist, SHA256SUMS.txt y
VALIDACION.md. Este último registra resultados, versiones, inventarios y hashes
propios del candidato, sin rutas personales ni coordinación interna. Los
inventarios detallados, diffs, logs y respaldos quedan fuera de los paquetes.
Se evita incluir el hash del sdist dentro del propio sdist.

## Condiciones nativas conservadas

Fedora GUI se observó con:

```sh
QT_QPA_PLATFORM=wayland QT_DISABLE_EMOJI_SEGMENTER=1 sentinel-gui
```

Se conservan terminal persistente en los casos Wayland, W1 inicial no
reconstruido, límites de dibujo sin ajuste y demás condiciones de
[validacion-fedora.md](validacion-fedora.md). Windows conserva su propio
[informe](validacion-windows.md). Un smoke offscreen del paquete instalado
no se interpreta como una nueva aceptación nativa o compatibilidad universal.
