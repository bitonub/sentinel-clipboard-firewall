# Avisos de terceros — SENTINEL 0.0.1

Revisión: 26 de octubre de 2026. Este aviso acompaña a LICENSE en el wheel y
sdist. **MIT corresponde al código propio de SENTINEL y su documentación propia**,
con Copyright (c) 2026 bitonub. No cambia licencias, avisos ni autoría de terceros.

## Contenido de la entrega

Nuestro wheel distribuye módulos Python de sentinel, metadatos, README como
descripción de metadatos, LICENSE y este aviso dentro de dist-info/licenses.
El sdist añade documentación, pruebas, herramientas y configuración del proyecto.
Los inventarios y comparación de contenidos del gate delimitan esos archivos.
No se incorporan paquetes PySide6/shiboken6, bibliotecas o plugins Qt, fuentes,
iconos, Python, wl-clipboard ni herramientas de build al interior de nuestros
artefactos. No hay instalador ni runtime embebido. Las capturas y auxiliares
locales de validación están excluidos.

La CLI base declara cero dependencias externas Python. El extra gui declara
PySide6>=6.11.2,<6.12: pip instala por separado los paquetes de Qt for Python
y sus binarios. La aplicación importa QtCore, QtGui y QtWidgets; el contenido
de los wheels externos es más amplio que esos imports. Ese contenido no se
relicencia como MIT por instalar SENTINEL.

## Dependencias GUI observadas

Los cuatro paquetes revisados, versión 6.11.2, identifican como equipo a
Qt for Python Team (pyside@qt-project.org). Su campo License declara literalmente:

`LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`

Esta declaración no es una elección de licencia para cada módulo Qt ni un
inventario exhaustivo de sus componentes nativos. Las bibliotecas/plugins
Qt y partes de Qt for Python tienen también avisos y licencias de otros autores.
Las referencias primarias para las versiones revisadas son:

- [Licencias de Qt for Python 6.11](https://doc.qt.io/qtforpython-6.11/licenses.html).
- [Terceros incluidos en Qt 6.11.2](https://doc.qt.io/qt-6.11/licenses-used-in-qt.html).

Los wheels siguientes se obtuvieron del índice/cache configurado en pip y se
inspeccionaron para identificar los paquetes Linux usados en la instalación
externa de comprobación. Sus SHA-256 identifican entradas de la verificación,
**no archivos incorporados a la entrega** ni un lock de todas las plataformas.

| Archivo externo Linux | SHA-256 |
|---|---|
| `pyside6-6.11.2-cp310-abi3-manylinux_2_34_x86_64.whl` | `dc6d03990489a5085842770718392ef5de36352d8f608d9a9fe03e60af4d7b66` |
| `pyside6_addons-6.11.2-cp310-abi3-manylinux_2_34_x86_64.whl` | `a8b00956925fbdeffc7052cf933506391289f35ac4f3f71a0a167ec195cd47b4` |
| `pyside6_essentials-6.11.2-cp310-abi3-manylinux_2_34_x86_64.whl` | `aaf9f25f0f324874085fa5b26a610318db8a8e243cf85bb3e5400595191c7778` |
| `shiboken6-6.11.2-cp310-abi3-manylinux_2_34_x86_64.whl` | `7a7a0a72a9ed26c9bf77d42246b1c736486befb8f31aa2fb29957ea4cdd1c1c2` |

En esos wheels los metadatos no enumeran License-File ni aparecen rutas de
licencia/notice en sus registros de archivos revisados. Esto no prueba que sus
fuentes originales carezcan de licencias y no permite certificar por sí solo
cumplimiento de las condiciones LGPL/GPL ni de los componentes nativos.
Las dependencias se conservan como distribuciones separadas sin alterar sus
archivos o avisos. No se copian aquí textos ajenos como si fueran MIT propio.
Una redistribución futura de Qt/PySide6 o de sus binarios requerirá revisar los
componentes exactos, sus textos, avisos y condiciones aplicables antes de hacerla;
no es un escenario aprobado ni implementado por esta entrega wheel/sdist.

## Prerrequisitos y herramientas externos

- Python y su biblioteca estándar: prerrequisito instalado por el usuario,
  no distribuido aquí. [Licencia de Python](https://docs.python.org/3/license.html).
- wl-clipboard: herramienta externa para Wayland; entorno aceptado 2.2.1,
  RPM Fedora wl-clipboard-2.2.1^git20251124.e808203-2.fc44.x86_64. No se incluye
  su binario ni código. Se conserva la referencia al [COPYING del proyecto](https://github.com/bugaevc/wl-clipboard/blob/master/COPYING).
- build, setuptools, packaging, pyproject_hooks y pip: herramientas externas
  de construcción/instalación; pip-audit es de auditoría. Sus paquetes no se
  incorporan al wheel o sdist por ejecutarlos. Las versiones utilizadas se
  registran en el informe de verificación, sin asignarles MIT de SENTINEL.

No se identificó material de terceros vendorizado en el inventario de fuentes
propias revisado; cualquier aviso legítimo preexistente se conserva. La revisión
se limita a lo que se entrega y a identificar dependencias externas: no declara
cumplimiento global del entorno del destinatario ni autoriza eliminar avisos de
sus paquetes. Si cambia el contenido distribuido, este alcance debe revisarse.
