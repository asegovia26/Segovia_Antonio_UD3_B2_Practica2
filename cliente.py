import json
import socket


HOST = "127.0.0.1"
PORT = 5000

TIMEOUT_SERVIDOR = 10


# ---------------------------------------------------------
# ENVÍO
# ---------------------------------------------------------

def enviar_json(conexion, contenido):
    """
    Envía un diccionario como JSON
    terminado en salto de línea.
    """

    mensaje = json.dumps(
        contenido,
        ensure_ascii=False
    ) + "\n"

    conexion.sendall(mensaje.encode("utf-8"))


# ---------------------------------------------------------
# RECEPCIÓN
# ---------------------------------------------------------

def recibir_linea(conexion):
    """
    Recibe una línea completa.
    Versión sencilla para un cliente que
    realiza una petición y espera una respuesta.
    """

    buffer = ""

    while "\n" not in buffer:
        datos = conexion.recv(1024)

        if not datos:
            return None

        buffer += datos.decode("utf-8")

    linea, resto = buffer.split(
        "\n",
        1
    )

    return linea


# ---------------------------------------------------------
# MOSTRAR RESPUESTA
# ---------------------------------------------------------

def mostrar_respuesta(respuesta):
    """
    Muestra una respuesta del servidor.
    """

    if respuesta.get("ok"):
        print(
            "Resultado:",
            respuesta.get("resultado")
        )

    else:
        print(
            "Error:",
            respuesta.get("error")
        )


# ---------------------------------------------------------
# MENÚ
# ---------------------------------------------------------

def mostrar_menu():
    print("\n" + "=" * 45)
    print("COMANDOS DISPONIBLES")
    print("=" * 45)

    print("1. Convertir a mayúsculas")
    print("2. Calcular longitud")
    print("3. Invertir texto")
    print("4. Enviar comando desconocido")
    print("5. Salir")


# ---------------------------------------------------------
# PROGRAMA PRINCIPAL
# ---------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("CLIENTE DE COMANDOS JSON")
    print("=" * 60)

    try:
        with socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        ) as cliente:

            cliente.settimeout(
                TIMEOUT_SERVIDOR
            )

            cliente.connect(
                (HOST, PORT)
            )

            print(
                f"Conectado con "
                f"{HOST}:{PORT}"
            )

            while True:
                mostrar_menu()

                opcion = input(
                    "Selecciona una opción: "
                )

                if opcion == "1":
                    comando = "MAYUSCULAS"

                elif opcion == "2":
                    comando = "LONGITUD"

                elif opcion == "3":
                    comando = "INVERTIR"

                elif opcion == "4":
                    comando = "DESCONOCIDO"

                elif opcion == "5":
                    comando = "SALIR"

                else:
                    print(
                        "Opción incorrecta."
                    )

                    continue

                if comando == "SALIR":
                    peticion = {
                        "comando": "SALIR"
                    }

                else:
                    texto = input(
                        "Introduce el texto: "
                    )

                    peticion = {
                        "comando": comando,
                        "texto": texto
                    }

                enviar_json(cliente, peticion)

                linea = recibir_linea(cliente)

                if linea is None:
                    print(
                        "El servidor ha cerrado "
                        "la conexión."
                    )
                    break

                respuesta = json.loads(linea)

                mostrar_respuesta(respuesta)

                if comando == "SALIR":
                    break

    except ConnectionRefusedError:
        print(
            "No se pudo conectar."
        )

        print(
            "Comprueba que el servidor "
            "está ejecutándose."
        )

    except socket.timeout:
        print(
            "El servidor no respondió "
            "dentro del tiempo máximo."
        )

    except ConnectionResetError:
        print(
            "El servidor interrumpió "
            "la conexión."
        )

    except json.JSONDecodeError:
        print(
            "El servidor ha enviado "
            "una respuesta JSON inválida."
        )

    except OSError as error:
        print(
            f"Error de red: {error}"
        )

    print("Cliente finalizado.")
