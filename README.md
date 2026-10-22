# SENTINEL Clipboard Firewall

Herramienta local para detectar y sanitizar direcciones IPv4 privadas en texto
proporcionado explícitamente por stdin. Requiere Python 3.11 o superior y usa
solo la biblioteca estándar durante la ejecución.

## Uso

Instala el proyecto con `pip install .` y ejecuta:

```sh
printf 'host=10.20.30.40 peer=10.20.30.40' | sentinel sanitize
# host=[PRIVATE_IP_1] peer=[PRIVATE_IP_1]

printf 'host=10.20.30.40' | sentinel scan
# [{"rule_id": "RFC1918_IPV4", "category": "infrastructure", "start": 5, "end": 16, "severity": "informational", "explanation": "Dirección IPv4 en un rango privado RFC 1918."}]
```

`scan` devuelve una lista JSON de hallazgos con posiciones de caracteres
`[inicio, fin)` y sin incluir los valores encontrados. `sanitize` conserva el
resto del texto y reutiliza una etiqueta para cada dirección repetida durante
la operación. Se admiten hasta 1 MiB de entrada UTF-8; errores y diagnósticos
van a stderr sin reproducir la entrada.

Solo se detectan IPv4 válidas de los rangos 10/8, 172.16/12 y 192.168/16.
No se hacen conexiones de red ni se ejecuta el texto de entrada. La ausencia
de hallazgos no garantiza que el texto sea seguro. `check-command`, el
portapapeles y la GUI están pendientes.

Los ejemplos y las pruebas usan exclusivamente datos sintéticos.
