import http.client
import ssl

# Configuración de la conexión
conn = http.client.HTTPSConnection("api.ultramsg.com", context=ssl._create_unverified_context())

# Configuración de los parámetros
token = "852p454ojw3halwp"  # Reemplaza con tu token de UltraMsg
instance_id = "instance101045"  # Reemplaza con tu ID de instancia
to = "+51902512657"  # Número de teléfono en formato internacional
body = "¡Hola! Esta es una prueba de la API de UltraMsg con Python."

# Preparar el payload
payload = f"token={token}&to={to}&body={body}"
payload = payload.encode('utf-8').decode('iso-8859-1')

# Configurar los headers
headers = {
    'content-type': "application/x-www-form-urlencoded"
}

# Enviar la solicitud
try:
    conn.request("POST", f"/{instance_id}/messages/chat", payload, headers)
    res = conn.getresponse()
    data = res.read()
    
    # Imprimir la respuesta
    print("Respuesta de la API:", data.decode("utf-8"))
except Exception as e:
    print("Error al enviar el mensaje:", str(e))
