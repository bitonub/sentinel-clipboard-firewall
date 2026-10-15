# Modelo de amenazas inicial

## Datos que protegemos

- Texto técnico proporcionado por el usuario.
- Credenciales que pueda contener.
- Información de infraestructura.
- Asociaciones entre valores originales y placeholders.

## Límites de confianza

Todo texto recibido se considera entrada no confiable.
Se analiza como datos y nunca como código ejecutable.

La terminal y el sistema operativo están fuera del control
de SENTINEL. Se supone que el equipo no está comprometido.

## Amenazas y controles

| Amenaza | Control | Limitación |
|---|---|---|
| Compartir información sensible accidentalmente | Detección y sanitización | Solo cubre las categorías implementadas |
| Ejecutar comandos recibidos | Análisis estático sin ejecución | El usuario puede ejecutar el comando por su cuenta |
| Filtrar originales mediante diagnósticos | No incluir la entrada en logs ni errores | La terminal puede conservar texto mostrado por el usuario |
| Persistir valores originales | Mapas efímeros por operación | Python no garantiza borrado seguro de memoria |
| Agotar memoria con entradas grandes | Lectura acotada a 1 MiB más un byte para detectar exceso | El límite no sustituye pruebas de rendimiento |
| Alterar texto ajeno al hallazgo | Sustituir únicamente intervalos validados | Los detectores pueden cometer errores |
| Generar falsa confianza | Documentar alcance y limitaciones | Ausencia de hallazgos no significa seguridad |

## Primer incremento: IPv4 privadas

Las direcciones privadas se consideran información de infraestructura,
no credenciales. Su detección tendrá severidad informativa.

Se comprobarán los rangos RFC 1918 explícitamente.
No se clasificarán automáticamente otras direcciones especiales
como privadas.

## Fuera de alcance

- Malware que ya se ejecuta en el equipo.
- Interceptar o bloquear todos los pegados.
- Detectar todos los formatos de secretos.
- Garantizar que un comando es seguro.
- Eliminar datos del historial del shell o del portapapeles.
- Borrar de forma garantizada valores sensibles de la RAM.

## Datos de desarrollo

Todos los ejemplos y casos de prueba serán sintéticos.
No se utilizarán datos internos de empresas ni de clientes.
