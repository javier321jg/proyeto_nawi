import cloudinary
import cloudinary.uploader
import cloudinary.api
import os

# Configuración de Cloudinary con tus credenciales
cloudinary.config(
    cloud_name="dxrt7dr1v",  # Reemplaza con tu "Cloud Name"
    api_key="457733397447258",  # Reemplaza con tu "API Key"
    api_secret="Y8EFVvYGT-5mXX-Jicfv_2tYQmM"  # Reemplaza con tu "API Secret"
)

def subir_imagen(ruta_imagen):
    """
    Función para subir una imagen a Cloudinary y obtener su URL pública.
    """
    try:
        # Subir la imagen
        respuesta = cloudinary.uploader.upload(ruta_imagen)
        print("Imagen subida exitosamente.")
        print("URL pública:", respuesta['secure_url'])
        return respuesta['secure_url']
    except Exception as e:
        print("Error al subir la imagen:", e)
        return None

# Prueba: Subir la imagen pytorch.png
if __name__ == "__main__":
    # Ruta completa a la imagen en tu proyecto
    ruta = os.path.join("static", "assets", "img", "pytorch.png")  # Ajusta según la estructura de tu proyecto
    if os.path.exists(ruta):
        print("Subiendo la imagen desde:", ruta)
        url = subir_imagen(ruta)
        if url:
            print("URL de la imagen cargada:", url)
    else:
        print("La imagen no se encuentra en la ruta especificada:", ruta)
