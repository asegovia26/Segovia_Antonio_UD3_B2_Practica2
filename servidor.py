import json
import logging
import socket
import threading


HOST = "127.0.0.1"
PORT = 5000

TIMEOUT_CLIENTE = 20

evento_parada = threading.Event()

lock_estadisticas = threading.Lock()

estadisticas = {
    "clientes_conectados": 0,
    "clientes_finalizados": 0,
    "comandos_correctos": 0,
    "errores": 0,
    "timeouts": 0
}


# ---------------------------------------------------------
# CONFIGURACIÓN DE LOGGING
# ---------------------------------------------------------

logger = logging.getLogger("servidor")

logger.setLevel(logging.INFO)

formato = logging.Formatter(
    "%(asctime)s | %(levelname)s | "
    "%(threadName)s | %(message)s"
)

manejador_consola = logging.StreamHandler()

manejador_consola.setFormatter(formato)

manejador_archivo = logging.FileHandler(
    "servidor.log",
    mode="w",
    encoding="utf-8"
)

manejador_archivo.setFormatter(formato)

logger.addHandler(manejador_consola)
logger.addHandler(manejador_archivo)


# ---------------------------------------------------------
# ESTADÍSTICAS
# ---------------------------------------------------------

def incrementar_estadistica(clave):
    """
    Incrementa una estadística compartida
    de forma segura.
    """

    with lock_estadisticas:
        estadisticas[clave] += 1


# ---------------------------------------------------------
# ENVÍO DE MENSAJES JSON
# ---------------------------------------------------------

def enviar_json(conexion, contenido):
    """
    Convierte un diccionario en JSON,
    añade el delimitador y lo envía.
    """

    mensaje = json.dumps(
        contenido,
        ensure_ascii=False
    ) + "\n"

    conexion.sendall(mensaje.encode("utf-8"))


# ---------------------------------------------------------
# PROCESAMIENTO DE COMANDOS
# ---------------------------------------------------------

def procesar_peticion(peticion):
    """
    Valida y procesa una petición.
    Devuelve un diccionario de respuesta.
    """

    # Comprobar que la petición es
    # un objeto JSON.
    if not isinstance(peticion, dict):
        return {
            "ok": False,
            "error": (
                "La petición debe ser "
                "un objeto JSON"
            )
        }

    comando = peticion.get("comando")

    texto = peticion.get("texto")

    if not isinstance(comando, str):
        return {
            "ok": False,
            "error": (
                "El campo comando es obligatorio"
            )
        }

    comando = comando.upper()

    # SALIR no necesita el campo texto.
    if comando == "SALIR":
        return {
            "ok": True,
            "resultado": (
                "Conexión finalizada"
            ),
            "cerrar": True
        }

    if not isinstance(texto, str):
        return {
            "ok": False,
            "error": (
                "El campo texto debe ser "
                "una cadena"
            )
        }

    if comando == "MAYUSCULAS":
        return {
            "ok": True,
            "resultado": texto.upper()
        }

    if comando == "LONGITUD":
        return {
            "ok": True,
            "resultado": len(texto)
        }

    if comando == "INVERTIR":
        return {
            "ok": True,
            "resultado": texto[::-1]
        }

    return {
        "ok": False,
        "error": (
            f"Comando desconocido: {comando}"
        )
    }


# ---------------------------------------------------------
# ATENCIÓN DE UN CLIENTE
# ---------------------------------------------------------

def atender_cliente(
    conexion,
    direccion_cliente
):
    """
    Gestiona la conversación completa
    con un cliente.
    """

    nombre_hilo = (
        threading.current_thread().name
    )

    incrementar_estadistica(
        "clientes_conectados"
    )

    logger.info(
        "Cliente conectado | direccion=%s",
        direccion_cliente
    )

    # Configurar un tiempo máximo
    # de inactividad.
    conexion.settimeout(
        TIMEOUT_CLIENTE
    )

    buffer = ""

    try:
        with conexion:

            while not evento_parada.is_set():

                try:
                    datos = conexion.recv(1024)

                except socket.timeout:
                    incrementar_estadistica(
                        "timeouts"
                    )

                    logger.warning(
                        "Timeout | cliente=%s | "
                        "limite=%ss",
                        direccion_cliente,
                        TIMEOUT_CLIENTE
                    )

                    enviar_json(
                        conexion,
                        {
                            "ok": False,
                            "error": (
                                "Tiempo de espera "
                                "agotado"
                            )
                        }
                    )

                    break

                if not datos:
                    logger.info(
                        "Cliente desconectado | "
                        "direccion=%s",
                        direccion_cliente
                    )

                    break

                buffer += datos.decode("utf-8")

                while "\n" in buffer:
                    linea, buffer = buffer.split(
                        "\n",
                        1
                    )

                    if not linea.strip():
                        continue

                    try:
                        peticion = json.loads(linea)

                    except json.JSONDecodeError as error:
                        incrementar_estadistica(
                            "errores"
                        )

                        logger.warning(
                            "JSON inválido | cliente=%s | "
                            "error=%s",
                            direccion_cliente,
                            error
                        )

                        enviar_json(
                            conexion,
                            {
                                "ok": False,
                                "error": "JSON inválido"
                            }
                        )

                        continue

                    respuesta = procesar_peticion(
                        peticion
                    )

                    enviar_json(
                        conexion,
                        respuesta
                    )

                    if respuesta["ok"]:
                        incrementar_estadistica(
                            "comandos_correctos"
                        )
                        logger.info(
                            "Comando procesado | cliente=%s | comando=%s",
                            direccion_cliente,
                            peticion.get("comando") if isinstance(peticion, dict) else None
                        )
                    else:
                        incrementar_estadistica(
                            "errores"
                        )
                        logger.warning(
                            "Petición con error | cliente=%s | error=%s",
                            direccion_cliente,
                            respuesta.get("error")
                        )

                    if respuesta.get("cerrar"):
                        logger.info(
                            "Cierre solicitado | cliente=%s",
                            direccion_cliente
                        )

                        return

    except UnicodeDecodeError as error:
        incrementar_estadistica("errores")

        logger.error(
            "Error de codificación | "
            "cliente=%s | error=%s",
            direccion_cliente,
            error
        )

    except ConnectionResetError:
        incrementar_estadistica("errores")

        logger.warning(
            "Conexión reiniciada | "
            "cliente=%s",
            direccion_cliente
        )

    except BrokenPipeError:
        incrementar_estadistica("errores")

        logger.warning(
            "No se pudo enviar la respuesta | "
            "cliente=%s",
            direccion_cliente
        )

    except OSError as error:
        incrementar_estadistica("errores")

        logger.error(
            "Error de socket | "
            "cliente=%s | error=%s",
            direccion_cliente,
            error
        )

    finally:
        incrementar_estadistica(
            "clientes_finalizados"
        )

        logger.info(
            "Worker finalizado | "
            "hilo=%s | cliente=%s",
            nombre_hilo,
            direccion_cliente
        )


# ---------------------------------------------------------
# MOSTRAR ESTADÍSTICAS
# ---------------------------------------------------------

def mostrar_estadisticas():
    print("\n" + "=" * 60)
    print("ESTADÍSTICAS DEL SERVIDOR")
    print("=" * 60)

    with lock_estadisticas:
        for clave, valor in estadisticas.items():
            print(
                f"{clave.replace('_', ' ').title()}: "
                f"{valor}"
            )


# ---------------------------------------------------------
# PROGRAMA PRINCIPAL
# ---------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("SERVIDOR JSON MULTICLIENTE")
    print("=" * 60)

    hilos_clientes = []

    try:
        with socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        ) as servidor:

            servidor.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_REUSEADDR,
                1
            )

            servidor.bind((HOST, PORT))

            servidor.listen()

            logger.info(
                "Servidor iniciado | "
                "direccion=%s:%s",
                HOST,
                PORT
            )

            while not evento_parada.is_set():

                try:
                    conexion, direccion = (
                        servidor.accept()
                    )

                except KeyboardInterrupt:
                    logger.warning(
                        "Parada solicitada "
                        "desde el teclado"
                    )

                    evento_parada.set()

                    break

                nombre_hilo = (
                    f"Cliente-{direccion[0]}-{direccion[1]}"
                )

                hilo = threading.Thread(
                    target=atender_cliente,
                    args=(conexion, direccion),
                    name=nombre_hilo
                )

                hilo.start()
                hilos_clientes.append(hilo)

    except OSError as error:
        logger.critical(
            "No se pudo iniciar el servidor | "
            "error=%s",
            error
        )

    finally:
        evento_parada.set()

        logger.info(
            "Esperando a los workers"
        )

        for hilo in hilos_clientes:
            hilo.join(timeout=3)

        mostrar_estadisticas()

        logger.info(
            "Servidor finalizado"
        )
