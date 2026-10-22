# SENTINEL Clipboard Firewall

Herramienta local para detectar y sanitizar IPv4 privadas y asignaciones de contraseña en texto
proporcionado explícitamente por stdin. Requiere Python 3.11 o superior y usa
solo la biblioteca estándar durante la ejecución.

## Uso

Instala el proyecto con `pip install .` y ejecuta:

```sh
printf 'host=10.20.30.40 peer=10.20.30.40' | sentinel sanitize
# host=[PRIVATE_IP_1] peer=[PRIVATE_IP_1]

printf 'host=10.20.30.40' | sentinel scan
# [{"rule_id": "RFC1918_IPV4", "category": "infrastructure", "start": 5, "end": 16, "severity": "informational", "explanation": "Dirección IPv4 en un rango privado RFC 1918."}]

printf 'password=Synthetic42 pwd=Synthetic42' | sentinel sanitize
# password=[PASSWORD_1] pwd=[PASSWORD_1]
```

`scan` devuelve una lista JSON de hallazgos con posiciones de caracteres
`[inicio, fin)` y sin incluir los valores encontrados. `sanitize` conserva el
resto del texto y reutiliza una etiqueta para cada valor repetido de la misma categoría durante
la operación. Se admiten hasta 1 MiB de entrada UTF-8; errores y diagnósticos
van a stderr sin reproducir la entrada.

Se detectan IPv4 válidas de los rangos 10/8, 172.16/12 y 192.168/16,
excluyendo las incrustadas en IPv6.

Las asignaciones admiten las claves completas `password`, `passwd` y `pwd`
(sin distinguir mayúsculas), opcionalmente entre comillas, con `=` o `:` y
espacios o tabuladores alrededor del separador. Los valores pueden ir entre
comillas simples o dobles en una sola línea, o sin comillas hasta un espacio,
coma, punto y coma, comilla, llave o corchete. Se conservan la clave, las
comillas y el resto del texto; solo se reemplaza el valor por `[PASSWORD_n]`.
Los valores vacíos, referencias completas `${NAME}` o `$NAME` y etiquetas
generadas se omiten. La numeración es independiente por categoría y operación;
las repeticiones se comparan literalmente, sin interpretar escapes.
Si una contraseña contiene una IPv4 privada, se informa y sustituye el valor
completo de la contraseña, evitando intervalos superpuestos.

La detección es textual: no interpreta lenguajes de configuración, comentarios
ni valores multilínea, y solo cubre las claves y formas descritas.
No se hacen conexiones de red ni se ejecuta el texto de entrada. La ausencia
de hallazgos no garantiza que el texto sea seguro. `check-command`, el
portapapeles y la GUI están pendientes.

Los ejemplos y las pruebas usan exclusivamente datos sintéticos.
