from flask import Flask, request, jsonify
import os
import time
import requests
import tempfile
import cloudinary
import cloudinary.uploader
from ultralytics import YOLO
from flask_sqlalchemy import SQLAlchemy
import json

# Configuración de Flask
app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_muy_segura'

# Configuración de Cloudinary
cloudinary.config(
    cloud_name="Tdxrt7dr1v",    # Reemplaza con tu Cloud Name
    api_key="U457733397447258",          # Reemplaza con tu API Key
    api_secret="Y8EFVvYGT-5mXX-Jicfv_2tYQmM"     # Reemplaza con tu API Secret
)

# Configuración de la base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:DAcnRAsSqsdiVCpYmgydAIbsnpsTTeBN@autorack.proxy.rlwy.net:27853/railway'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Configuración para cargar archivos
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Modelo YOLO
model = None

# Modelo para detecciones en la base de datos
class Detection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_original_url = db.Column(db.String(255), nullable=False)
    image_processed_url = db.Column(db.String(255), nullable=False)
    detections = db.Column(db.Text, nullable=False)  # JSON con los resultados
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_model():
    """Carga el modelo YOLO desde un archivo local."""
    global model
    try:
        model_path = os.path.join(os.getcwd(), 'modelo1.pt')
        if not os.path.exists(model_path):
            raise Exception("El archivo del modelo no existe en la carpeta local")
        
        model = YOLO(model_path)
        print("Modelo cargado exitosamente desde almacenamiento local")
    except Exception as e:
        print(f"Error al cargar el modelo: {e}")

# Configuración de UltraMsg
token = "852p454ojw3halwp"
instance_id = "instance101045"

def send_whatsapp_message(phone_number, message):
    """Envía un mensaje de WhatsApp usando UltraMsg."""
    try:
        url = f"https://api.ultramsg.com/{instance_id}/messages/chat"
        payload = {
            'token': token,
            'to': phone_number,
            'body': message
        }
        response = requests.post(url, data=payload)
        return response.json()
    except Exception as e:
        print(f"Error al enviar el mensaje de WhatsApp: {e}")
        return None

@app.route('/', methods=['GET', 'POST'])
def home():
    """Página de inicio para verificar que el servidor está activo."""
    if request.method == 'POST':
        return jsonify({"message": "POST request recibido correctamente"}), 200
    return jsonify({"message": "El servidor Flask está activo y funcionando."}), 200

@app.route('/ultramsg_webhook', methods=['GET', 'POST'])
def ultramsg_webhook():
    if request.method == 'GET':
        return jsonify({"message": "Webhook endpoint está activo. Use POST para enviar datos."}), 200
    
    data = request.get_json()
    if data is None:
        return jsonify({"error": "No se recibieron datos JSON"}), 400

    try:
        # Extraer información del mensaje entrante
        message_type = data.get('type')
        from_number = data.get('from')
        message_body = data.get('body')
        media_url = data.get('media')

        # Verificar si el mensaje es una imagen
        if message_type == 'image' and media_url:
            # Descargar la imagen desde la URL proporcionada
            response = requests.get(media_url)
            if response.status_code == 200:
                # Guardar la imagen temporalmente
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                    tmp_file.write(response.content)
                    tmp_file_path = tmp_file.name

                # Procesar la imagen con el modelo YOLO
                results = model.predict(tmp_file_path)
                detections = [
                    {"class": results[0].names[int(box.cls)], "confidence": float(box.conf)} 
                    for box in results[0].boxes
                ]

                # Subir la imagen procesada a Cloudinary
                processed_image_path = results[0].plot()
                processed_upload_result = cloudinary.uploader.upload(
                    processed_image_path,
                    folder="processed/wsp",
                    public_id=f"processed_wsp_{int(time.time())}"
                )
                processed_url = processed_upload_result['secure_url']

                # Guardar los resultados en la base de datos
                detection = Detection(
                    image_original_url=media_url,
                    image_processed_url=processed_url,
                    detections=json.dumps(detections)
                )
                db.session.add(detection)
                db.session.commit()

                # Enviar los resultados de vuelta al usuario por WhatsApp
                message = f"Hola, tu imagen ha sido procesada exitosamente.\nResultados:\n{json.dumps(detections, indent=2)}\nImagen procesada: {processed_url}"
                whatsapp_response = send_whatsapp_message(from_number, message)

                # Eliminar el archivo temporal
                os.remove(tmp_file_path)

                return jsonify({
                    "status": "success",
                    "message": "Imagen procesada correctamente",
                    "detections": detections,
                    "processed_url": processed_url
                }), 200
            else:
                send_whatsapp_message(from_number, "No se pudo descargar la imagen. Por favor, inténtalo de nuevo.")
                return jsonify({"error": "No se pudo descargar la imagen"}), 400
        else:
            # Si el mensaje no es una imagen
            send_whatsapp_message(from_number, "Por favor, envía una imagen para procesar.")
            return jsonify({
                "status": "ignored",
                "message": "El mensaje no es una imagen",
                "type": message_type
            }), 200
    except Exception as e:
        print(f"Error al procesar el mensaje entrante: {e}")
        if from_number:
            send_whatsapp_message(from_number, "Ocurrió un error al procesar tu imagen. Por favor, inténtalo de nuevo.")
        return jsonify({"error": str(e)}), 500

@app.route('/upload_wsp', methods=['POST'])
def upload_image_wsp():
    """Ruta para cargar una imagen desde un formulario y enviar un mensaje."""
    if 'file' not in request.files or 'phone_number' not in request.form:
        return jsonify({"error": "Se necesita un archivo y un número de teléfono"}), 400
    
    file = request.files['file']
    phone_number = request.form['phone_number']
    
    if file.filename == '':
        return jsonify({"error": "No se seleccionó ningún archivo"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": "Tipo de archivo no permitido"}), 400
    
    try:
        # Guardar el archivo temporalmente
        filename = file.filename
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # Subir imagen original a Cloudinary
        upload_result = cloudinary.uploader.upload(
            filepath,
            folder="uploads",
            public_id=f"{int(time.time())}_{os.path.splitext(filename)[0]}"
        )
        cloudinary_url = upload_result['secure_url']

        # Realizar predicción con YOLO
        results = model.predict(filepath)
        detections = [
            {"class": result.names[int(box.cls)], "confidence": float(box.conf)} 
            for result in results for box in result.boxes
        ]

        # Subir imagen procesada a Cloudinary
        processed_image_path = results[0].plot()
        processed_upload_result = cloudinary.uploader.upload(
            processed_image_path,
            folder="processed/wsp",
            public_id=f"processed_wsp_{int(time.time())}"
        )
        processed_url = processed_upload_result['secure_url']

        # Guardar en la base de datos
        detection = Detection(
            image_original_url=cloudinary_url,
            image_processed_url=processed_url,
            detections=json.dumps(detections)
        )
        db.session.add(detection)
        db.session.commit()

        # Enviar mensaje de WhatsApp
        message = f"Hola, tu imagen ha sido procesada exitosamente.\nResultados:\n{json.dumps(detections, indent=2)}\nImagen procesada: {processed_url}"
        whatsapp_response = send_whatsapp_message(phone_number, message)

        # Limpiar archivo temporal
        os.remove(filepath)

        return jsonify({
            "message": "Imagen procesada exitosamente",
            "cloudinary_url": cloudinary_url,
            "processed_url": processed_url,
            "detections": detections,
            "whatsapp_response": whatsapp_response
        })
    except Exception as e:
        return jsonify({"error": f"Error al procesar la imagen: {str(e)}"}), 500

@app.errorhandler(405)
def method_not_allowed(e):
    """Manejador personalizado para errores 405 Method Not Allowed"""
    return jsonify({
        "error": "Método no permitido",
        "message": "El método HTTP utilizado no está permitido para esta ruta.",
        "allowed_methods": e.valid_methods
    }), 405

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Crear tablas en la base de datos si no existen
        load_model()     # Cargar el modelo YOLO
    app.run(debug=True, port=5030)