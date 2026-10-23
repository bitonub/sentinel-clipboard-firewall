# Especificación inicial de SENTINEL

## Objetivo

Ayudar a usuarios técnicos a revisar texto antes de compartirlo
y reconocer patrones peligrosos en comandos antes de ejecutarlos.

## Primera versión

Interfaz de terminal con tres operaciones:

- scan: detectar información potencialmente sensible.
- sanitize: sustituir los valores detectados por placeholders.
- check-command: explicar patrones de riesgo sin ejecutar la entrada.

Inicialmente, el texto se recibirá mediante stdin.
La integración directa con el portapapeles llegará después.

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

## Limitaciones

La herramienta detectará únicamente las categorías implementadas.
La ausencia de hallazgos no garantiza que el texto sea seguro.
La versión inicial requiere una acción explícita del usuario.
