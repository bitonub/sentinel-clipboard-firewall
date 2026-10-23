# SENTINEL Clipboard Firewall

Herramienta local para detectar y sanitizar IPv4 privadas, asignaciones de
contraseña, tokens Bearer y credenciales en URLs PostgreSQL en texto
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

printf 'Authorization: Bearer Synthetic42' | sentinel sanitize
# Authorization: Bearer [BEARER_TOKEN_1]

printf 'postgres://synthetic:example42@db.example:5432/app' | sentinel sanitize
# postgres://[POSTGRES_USER_1]:[POSTGRES_PASSWORD_1]@db.example:5432/app
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

Se admiten encabezados literales `Authorization: Bearer <token>`, sin distinguir
mayúsculas, con espacios o tabuladores en una sola línea. El token puede usar
letras ASCII, dígitos, `-._~+/` y signos `=` al final. No se aceptan prefijos de
tokens con caracteres fuera de ese conjunto. Solo se sustituye el token por
`[BEARER_TOKEN_n]`, conservando encabezado, esquema y espacios. Los tokens
vacíos y las etiquetas existentes se omiten; las etiquetas Bearer y de
contraseña presentes en el texto se reservan antes de numerar valores nuevos.
Un token que también sea una IPv4 se sustituye como Bearer; un encabezado
dentro del valor de una contraseña se sustituye como parte de esa contraseña.
No se interpretan representaciones JSON de encabezados ni encabezados plegados.

En candidatas `postgres://` y `postgresql://` con userinfo se sustituyen el usuario
y la contraseña no vacíos por `[POSTGRES_USER_n]` y `[POSTGRES_PASSWORD_n]`.
Las etiquetas existentes se reservan por tipo y operación. Los valores con
percent-encoding se comparan literalmente, sin decodificarlos. Se oculta un
userinfo inequívoco incluso con puertos inválidos, hosts malformados o varios
hosts, conservando el resto de la candidata. No se valida la conectividad ni
la configuración del servidor. Si el userinfo es ambiguo (por ejemplo, varios
`@` en la autoridad o escapes inválidos), se sustituye la candidata completa
por `[POSTGRES_URL_n]`.
Dentro de estas candidatas con userinfo no se aplican las otras reglas, para
evitar sustituciones parciales. Si una asignación de contraseña contiene una
URL o termina dentro de ella, su intervalo se amplía para cubrir la URL entera.
Las URLs sin userinfo siguen permitiendo la detección IPv4. La regla cubre
solo userinfo en la autoridad: no analiza credenciales en la consulta, sockets
Unix ni todas las variantes de libpq; las candidatas terminan en espacios,
comillas o delimitadores angulares.

La detección es textual: no interpreta lenguajes de configuración, comentarios
ni valores multilínea, y solo cubre las claves y formas descritas.
No se hacen conexiones de red ni se ejecuta el texto de entrada. La ausencia
de hallazgos no garantiza que el texto sea seguro. `check-command`, el
portapapeles y la GUI están pendientes.

Los ejemplos y las pruebas usan exclusivamente datos sintéticos.
