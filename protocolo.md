# Protocolo de Comunicación — Servidor de Comandos JSON Multicliente

Este documento especifica el protocolo de aplicación utilizado por el servidor y los clientes de la práctica **UD3. Bloque 2. Práctica 2: Servidor de comandos JSON multicliente**.

---

## 1. Dirección y puerto

| Parámetro | Valor |
| :--- | :--- |
| Dirección IP (Host) | `127.0.0.1` (localhost / loopback) |
| Puerto TCP | `5000` |

El servidor enlaza el socket de escucha en `127.0.0.1:5000` utilizando `SO_REUSEADDR` para agilizar el reinicio tras el cierre.

---

## 2. Protocolo de transporte (TCP)

La comunicación se realiza sobre **TCP** (`socket.AF_INET`, `socket.SOCK_STREAM`):

- Garantiza entrega ordenada, fiable y sin pérdida de datos.
- Transmite un **flujo continuo de bytes** (*byte stream*), sin noción nativa de fronteras de mensaje.
- Cada cliente mantiene una conexión TCP persistente sobre la que puede enviar múltiples peticiones secuenciales (patrón petición-respuesta) hasta que envíe `SALIR`, cierre el socket o expire su tiempo de inactividad.
- El servidor atiende múltiples clientes de forma simultánea asignando un hilo trabajador (*worker*) independiente por cada conexión aceptada.

---

## 3. Codificación de caracteres (UTF-8)

Todos los mensajes intercambiados entre cliente y servidor se codifican y decodifican en **UTF-8**.

- Al serializar JSON se utiliza `ensure_ascii=False` para conservar caracteres Unicode (tildes, eñes, símbolos) de forma legible antes de codificar a bytes UTF-8.
- Si el servidor recibe bytes que no constituyen una secuencia UTF-8 válida, captura `UnicodeDecodeError`, incrementa el contador de errores, registra el incidente en `servidor.log` y cierra la conexión de ese cliente.

---

## 4. Formato de mensajes (JSON)

Cada mensaje de aplicación es un único **objeto JSON** (*JSON object*) serializado en una sola línea:

- Los diccionarios de Python se serializan mediante `json.dumps(contenido, ensure_ascii=False)`.
- Las líneas recibidas se deserializan mediante `json.loads(linea)`.
- Si una línea recibida no es un JSON sintácticamente válido, el servidor captura `json.JSONDecodeError`, responde con un mensaje de error (`"JSON inválido"`) y mantiene abierta la conexión para permitir futuras peticiones válidas.

---

## 5. Delimitador de mensaje (`\n`)

Dado que TCP es un flujo de bytes y una llamada a `recv()` puede devolver un mensaje fragmentado o varios mensajes concatenados, el protocolo emplea el carácter de salto de línea **`\n`** como delimitador de fin de mensaje (*NDJSON / JSON Lines*).

- Cada emisor añade `\n` al final del objeto JSON antes de llamar a `sendall()`.
- El receptor acumula los fragmentos decodificados en un **búfer** de texto y extrae cada mensaje completo mediante un bucle `while "\n" in buffer:` con `buffer.split("\n", 1)`.
- Las líneas vacías o compuestas únicamente por espacios se descartan.

---

## 6. Estructura de petición

Toda petición enviada por el cliente debe ser un objeto JSON con los siguientes campos:

| Campo | Tipo | Obligatorio | Descripción |
| :--- | :--- | :--- | :--- |
| `comando` | `string` | Sí | Nombre de la operación a ejecutar (insensible a mayúsculas/minúsculas). |
| `texto` | `string` | Sí, salvo en `SALIR` | Cadena de texto sobre la que se aplica el comando. |

### Ejemplo de petición

```json
{"comando": "MAYUSCULAS", "texto": "Hola servidor"}
```

*(seguido de `\n`)*

---

## 7. Estructura de respuesta correcta

Cuando la petición es válida y se ejecuta correctamente, el servidor responde con un objeto JSON con:

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `ok` | `boolean` | Siempre `true`. |
| `resultado` | `string` o `number` | Resultado de la operación (`int` para `LONGITUD`, `str` para el resto). |
| `cerrar` | `boolean` (opcional) | Presente con valor `true` únicamente en la respuesta al comando `SALIR`. |

### Ejemplo de respuesta correcta

```json
{"ok": true, "resultado": "HOLA SERVIDOR"}
```

*(seguido de `\n`)*

---

## 8. Estructura de respuesta de error

Si la petición contiene JSON malformado, no es un objeto JSON, carece de campos obligatorios, tiene tipos incorrectos, solicita un comando desconocido o se agota el tiempo de espera, el servidor responde con:

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `ok` | `boolean` | Siempre `false`. |
| `error` | `string` | Mensaje descriptivo del error producido. |

### Ejemplos de respuesta de error

```json
{"ok": false, "error": "Comando desconocido: BORRAR"}
{"ok": false, "error": "El campo texto debe ser una cadena"}
{"ok": false, "error": "El campo comando es obligatorio"}
{"ok": false, "error": "JSON inválido"}
{"ok": false, "error": "Tiempo de espera agotado"}
```

*(cada uno seguido de `\n`)*

---

## 9. Comandos admitidos

| Comando | Requiere `texto` | Tipo de `resultado` | Funcionamiento | Ejemplo |
| :--- | :--- | :--- | :--- | :--- |
| `MAYUSCULAS` | Sí (`str`) | `string` | Convierte `texto` a mayúsculas (`texto.upper()`). | `"Hola"` → `"HOLA"` |
| `LONGITUD` | Sí (`str`) | `integer` | Devuelve el número de caracteres de `texto` (`len(texto)`). | `"Hola"` → `4` |
| `INVERTIR` | Sí (`str`) | `string` | Invierte el orden de los caracteres de `texto` (`texto[::-1]`). | `"Hola"` → `"aloH"` |
| `SALIR` | No | `string` | Solicita el cierre ordenado de la conexión de ese cliente. | `"Conexión finalizada"` |

Cualquier otro valor en `comando` devuelve un error `"Comando desconocido: <COMANDO>"`.

---

## 10. Funcionamiento de `SALIR`

El comando `SALIR` implementa un cierre ordenado a nivel de aplicación:

1. El cliente envía `{"comando": "SALIR"}\n` (no requiere el campo `texto`).
2. El servidor valida el comando y genera la respuesta `{"ok": true, "resultado": "Conexión finalizada", "cerrar": true}\n`.
3. El servidor envía la respuesta al cliente antes de cerrar el socket, incrementando `comandos_correctos` y registrando `"Cierre solicitado"` en `servidor.log`.
4. Al detectar `respuesta.get("cerrar")`, el hilo *worker* sale de `atender_cliente()`, cierra el socket conectado mediante el bloque `with conexion:`, incrementa `clientes_finalizados` y registra `"Worker finalizado"`.
5. El cliente recibe la respuesta, la muestra por pantalla y sale de su bucle cerrando su extremo del socket.
6. El hilo principal del servidor continúa activo aceptando nuevas conexiones sin afectar al resto de clientes conectados.

---

## 11. Política de timeout

Para evitar que clientes inactivos consuman hilos y descriptores de socket indefinidamente:

- **Servidor (`TIMEOUT_CLIENTE = 20` segundos):** cada socket conectado configura `conexion.settimeout(20)`. Si transcurren 20 segundos sin recibir datos en `recv(1024)`:
  1. Se captura `socket.timeout`.
  2. Se incrementa de forma segura la estadística `timeouts`.
  3. Se registra una advertencia (`WARNING`) en `servidor.log`.
  4. Se envía al cliente el aviso JSON `{"ok": false, "error": "Tiempo de espera agotado"}\n`.
  5. Se cierra únicamente la conexión de ese cliente y finaliza su hilo *worker*, sin detener el servidor ni afectar a otros clientes.
- **Cliente (`TIMEOUT_SERVIDOR = 10` segundos):** el cliente configura `cliente.settimeout(10)` para detectar si el servidor no responde dentro del tiempo máximo esperado, informando al usuario y finalizando limpiamente.
