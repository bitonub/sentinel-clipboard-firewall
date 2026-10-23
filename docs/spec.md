# Especificación inicial de SENTINEL

## Objetivo

Ayudar a usuarios técnicos a revisar texto antes de compartirlo
y reconocer patrones peligrosos en comandos antes de ejecutarlos.

## Primera versión

Interfaz de terminal con tres operaciones:

- scan: detectar información potencialmente sensible.
- sanitize: sustituir los valores detectados por placeholders.
- check-command: explicar patrones de riesgo sin ejecutar la entrada.

Las tres operaciones reciben texto mediante stdin. La orden explícita
`clipboard sanitize` lee y sanitiza texto del portapapeles Wayland.

## Primer incremento funcional

Detectar y sanitizar direcciones IPv4 de estos rangos privados:

- 10.0.0.0/8
- 172.16.0.0/12
- 192.168.0.0/16

Una dirección repetida debe recibir el mismo placeholder
durante una operación.

Ejemplo:

Entrada:
host=10.20.30.40 peer=10.20.30.40

Salida:
host=[PRIVATE_IP_1] peer=[PRIVATE_IP_1]

Las direcciones públicas y las IPv4 inválidas no se modificarán.
Las IPv6 quedan fuera de este primer incremento.

## Invariantes de seguridad

- Nunca ejecutar el texto analizado.
- No realizar conexiones de red durante el análisis.
- No registrar el contenido original.
- No persistir valores originales ni mapas de placeholders.
- No requerir privilegios de administrador.
- Utilizar exclusivamente datos sintéticos en ejemplos y pruebas.
- Limitar la entrada a 1 MiB y rechazar entradas mayores.

## Comprobaciones del primer incremento

- Detectar direcciones de los tres rangos privados.
- Respetar los límites de cada rango.
- Ignorar direcciones públicas e inválidas.
- Mantener placeholders consistentes para valores repetidos.
- Conservar intacto el texto restante.
- Sanitizar dos veces produce el mismo resultado que una vez.

## Reglas iniciales de Command Guard

`check-command` analiza stdin como texto y reporta `CF-BASH-001` con severidad
alta cuando identifica una descarga con curl o wget entregada por pipe
directamente a bash o sh. La salida JSON incluye explicación y sugerencia de
revisión previa del archivo, sin incluir el comando original. Aplica el mismo
límite de 1 MiB y las invariantes de seguridad del resto de la CLI.

`--shell bash|powershell` selecciona el analizador; Bash es el predeterminado.
Con `--shell powershell`, `CF-PS-001` reporta descargas con URL literal HTTP(S)
mediante Invoke-WebRequest o Invoke-RestMethod canalizadas directamente a
Invoke-Expression. Admite iwr, irm e iex sin distinguir mayúsculas y omite
descargas a archivo con -OutFile. No ejecuta ni expande la entrada; conserva
el mismo formato de metadatos y política de privacidad que la regla Bash.

Son heurísticas iniciales, no parsers completos. Sus formas admitidas
y limitaciones se describen en README.md; no garantiza seguridad ante un
resultado vacío.

## Sanitización explícita del portapapeles

`sentinel clipboard sanitize` utiliza el motor existente y escribe solo si el
texto cambia. La terminal muestra únicamente estado y número de hallazgos.
Lee como máximo 1 MiB más un byte, valida UTF-8 y no inicia la escritura ante
errores de lectura, tamaño, codificación o sanitización. El adaptador invoca
solo wl-paste y wl-copy con argumentos fijos, shell=False y tiempos límite,
sin enviar datos en argumentos ni reproducir sus diagnósticos. El núcleo
permanece independiente de subprocess y del portapapeles.
La lectura/comunicación tiene un plazo de 5 segundos, con hasta 2 segundos
adicionales de espera de terminación durante la limpieza. Si no se confirma
la terminación se comunica un error seguro sin esperar indefinidamente;
un fallo de limpieza no sustituye un error principal ya controlado.

## GUI mínima opcional

sentinel-gui requiere el extra gui (PySide6); la instalación base conserva la
CLI sin Qt. Ofrece Inspeccionar, Sanitizar y Analizar comando con selector
Bash/PowerShell solo para comandos. Entrada y salida son texto plano, la salida
es de solo lectura y la entrada aceptada tiene un límite de 1 MiB UTF-8.
Inspección y Command Guard muestran hasta 200 hallazgos sin valores originales,
con total y cantidad mostrada. La salida sanitizada se conserva completa incluso
si supera el límite de entrada. Editar descarta resultados anteriores y pendientes.

Una sola operación se ejecuta fuera del hilo de interfaz. El cierre se aplaza
sin bloquear hasta que termine el trabajador, incluida su terminación nativa.
No se ejecuta la entrada ni se usa red. Los errores no incluyen contenido.
No hay persistencia, historial propio, bandeja, monitorización ni operaciones
automáticas de portapapeles. Copiar y pegar manualmente están permitidos.

## Limitaciones

La herramienta detectará únicamente las categorías implementadas.
La ausencia de hallazgos no garantiza que el texto sea seguro.
La versión inicial requiere una acción explícita del usuario.
