# Arquitectura inicial

## Flujo de datos

stdin → CLI → motor → resultado

La CLI recibe texto UTF-8 y limita la entrada a 1 MiB.
El núcleo recibe texto y devuelve resultados sin acceder
a la terminal, al portapapeles, al disco ni a la red.

## Componentes

- CLI: interpreta opciones, valida la entrada y presenta resultados.
- Detector: identifica valores y sus posiciones en el texto.
- Sanitizador: sustituye los intervalos detectados.
- Command Guard: tokeniza comandos como datos y devuelve metadatos de riesgo
  y sugerencias sin conservar el comando en los hallazgos. La regla inicial
  `CF-BASH-001` busca descargas entregadas por pipe directo a Bash o sh.

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

## Interfaces posteriores

El portapapeles y la GUI utilizarán el mismo núcleo.
El núcleo no dependerá de esas interfaces.
