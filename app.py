# Imports existentes
from flask import Flask, render_template, request, redirect, send_file, url_for, Response
from flask import send_from_directory, jsonify, flash, session, make_response, abort
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from ultralytics import YOLO
from datetime import datetime
import argparse, io, json, os, shutil, time, base64, tempfile, requests
from PIL import Image
import cv2
import numpy as np
import pymysql
from functools import wraps
from models import db, Detection, DiseaseDetection, User, WebcamDetection
from models import WebcamFrameDetection, DiseaseDescription
from xhtml2pdf import pisa
# Decorador para requerir login
from functools import wraps
from flask import session, redirect, url_for, flash

# Nuevos imports para MongoDB
from pymongo import MongoClient
import gridfs
from bson.objectid import ObjectId


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder a esta página', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Inicialización del modelo
model = None

# Configuración de MongoDB Atlas
MONGO_URI = "mongodb://lala321ser:EXYZkbZbJuEFoMKg@atlas-sql-674bee042452c33b0bda6abb-q1bfp.a.query.mongodb.net/filestorage?ssl=true&authSource=admin"
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client.filestorage
fs = gridfs.GridFS(mongo_db)

# Mantener configuración existente
app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_muy_segura'

# Configuraciones existentes
UPLOAD_FOLDER = 'uploads'
PREDICT_FOLDER = 'runs/detect/predict'
JS_FOLDER = 'static/assets/js'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Configuración de la base de datos para Railway (mantener MySQL)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:DAcnRAsSqsdiVCpYmgydAIbsnpsTTeBN@autorack.proxy.rlwy.net:27853/railway'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar bases de datos
pymysql.install_as_MySQLdb()
db.init_app(app)

# Funciones de modelo existentes
def download_model():
    """Descarga el modelo desde Hugging Face"""
    url = "https://huggingface.co/javier233455/fresas/resolve/main/modelo1.pt"
    model_path = os.path.join(tempfile.gettempdir(), 'Modelo1.pt')
    
    try:
        print("Descargando modelo desde Hugging Face...")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(model_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print("Modelo descargado exitosamente")
        return model_path
    except Exception as e:
        print(f"Error al descargar el modelo: {e}")
        return None

def load_model():
    """Carga el modelo YOLO"""
    global model
    try:
        model_path = download_model()
        if model_path and os.path.exists(model_path):
            model = YOLO(model_path)
            print("Modelo YOLO cargado exitosamente")
            return True
        else:
            print("No se pudo encontrar o descargar el modelo")
            return False
    except Exception as e:
        print(f"Error al cargar el modelo YOLO: {e}")
        return False

# Nuevas funciones para MongoDB
def save_file_to_mongodb(file_data, filename, file_type='image'):
    """Guarda un archivo en MongoDB GridFS"""
    try:
        file_id = fs.put(
            file_data,
            filename=filename,
            file_type=file_type,
            upload_date=datetime.now()
        )
        return str(file_id)
    except Exception as e:
        print(f"Error al guardar archivo en MongoDB: {e}")
        return None

def get_file_from_mongodb(file_id):
    """Recupera un archivo desde MongoDB GridFS"""
    try:
        return fs.get(ObjectId(file_id))
    except Exception as e:
        print(f"Error al recuperar archivo de MongoDB: {e}")
        return None

def cleanup_files():
    """Limpia archivos temporales si es necesario"""
    try:
        temp_files = mongo_db.fs.files.find({"upload_date": {"$lt": datetime.now() - timedelta(days=1)}})
        for file in temp_files:
            fs.delete(file._id)
    except Exception as e:
        print(f"Error en limpieza de archivos: {e}")
# Funciones existentes modificadas para usar MongoDB
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_detections(results, file_id, user_id):
    """Procesa las detecciones y guarda en la base de datos"""
    detections = []
    diseases_detected = []
    
    # Mantener el registro en MySQL para compatibilidad
    detection_record = Detection(
        image_path=file_id,  # Ahora guardamos el ID de MongoDB
        total_detections=len(results[0].boxes),
        has_diseases=False,
        user_id=user_id
    )
    db.session.add(detection_record)
    db.session.commit()
    
    print("Procesando detecciones...")
    
    for result in results:
        for box in result.boxes:
            class_name = result.names[int(box.cls)]
            confidence = float(box.conf)
            
            print(f"Clase detectada: {class_name}")
            
            try:
                disease_info = DiseaseDescription.query.filter_by(name=class_name).first()
                
                if disease_info is None:
                    disease_info = DiseaseDescription.query.filter(
                        DiseaseDescription.name.strip() == class_name.strip()
                    ).first()
                
                print(f"Resultado de búsqueda: {disease_info}")
                
            except Exception as e:
                print(f"Error al buscar en la BD: {str(e)}")
                disease_info = None
            
            detection = {
                "class": class_name,
                "confidence": confidence
            }
            
            if disease_info:
                detection["disease_info"] = {
                    "short_description": disease_info.short_description,
                    "cause": disease_info.cause,
                    "effects": disease_info.effects,
                    "source": disease_info.source,
                    "recommendations": disease_info.recommendations
                }
            
            detections.append(detection)
            
            if "sana" not in class_name.lower():
                detection_record.has_diseases = True
                diseases_detected.append(class_name)
                
                disease_detection = DiseaseDetection(
                    detection_id=detection_record.id,
                    disease_name=class_name,
                    confidence=confidence,
                    user_id=user_id
                )
                db.session.add(disease_detection)
    
    detection_record.diseases_detected = ','.join(diseases_detected) if diseases_detected else ''
    db.session.commit()
    
    # Guardar metadata adicional en MongoDB
    try:
        mongo_db.detections_metadata.insert_one({
            'mysql_detection_id': detection_record.id,
            'file_id': file_id,
            'detections': detections,
            'timestamp': datetime.now(),
            'user_id': user_id
        })
    except Exception as e:
        print(f"Error al guardar metadata en MongoDB: {e}")
    
    return detections

def process_image(file):
    """Procesa una imagen y la guarda en MongoDB"""
    try:
        # Leer y procesar la imagen
        img_bytes = file.read()
        
        # Guardar imagen original en MongoDB
        original_id = save_file_to_mongodb(img_bytes, file.filename, 'original_image')
        if not original_id:
            raise Exception("Error al guardar imagen original en MongoDB")
        
        # Procesar con YOLO
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Convertir PNG a JPG si es necesario
        if file.filename.lower().endswith('.png'):
            img_jpg = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            _, img_encoded = cv2.imencode('.jpg', img_jpg)
            img_bytes = img_encoded.tobytes()
        
        results = model(img)
        
        # Guardar imagen procesada
        processed_img = results[0].plot()
        _, processed_encoded = cv2.imencode('.jpg', processed_img)
        processed_id = save_file_to_mongodb(
            processed_encoded.tobytes(),
            f"processed_{file.filename}",
            'processed_image'
        )
        
        if not processed_id:
            raise Exception("Error al guardar imagen procesada en MongoDB")
        
        # Guardar relación entre imágenes
        mongo_db.image_relations.insert_one({
            'original_id': original_id,
            'processed_id': processed_id,
            'timestamp': datetime.now(),
            'filename': file.filename
        })
        
        return original_id, processed_id, results
        
    except Exception as e:
        print(f"Error en process_image: {e}")
        return None, None, None

def get_detection_images(detection_id):
    """Recupera las imágenes asociadas a una detección"""
    try:
        detection = Detection.query.get(detection_id)
        if not detection:
            return None, None
        
        # Buscar las imágenes en MongoDB
        relation = mongo_db.image_relations.find_one({
            'original_id': detection.image_path
        })
        
        if not relation:
            return None, None
        
        return relation['original_id'], relation['processed_id']
        
    except Exception as e:
        print(f"Error al recuperar imágenes: {e}")
        return None, None
# Rutas principales modificadas para usar MongoDB
@app.route("/predict_img", methods=["GET", "POST"])
@login_required
def predict_img():
    print("Accediendo a predict_img")
    print(f"Sesión actual: {session}")
    
    if request.method == "POST":
        if 'file' not in request.files:
            return render_template('index.html', error="No se ha enviado ningún archivo")
        
        file = request.files['file']
        if file.filename == '':
            return render_template('index.html', error="No se ha seleccionado ningún archivo")
        
        if not allowed_file(file.filename):
            return render_template('index.html', error="Tipo de archivo no permitido")
        
        try:
            # Procesar imagen usando MongoDB
            original_id, processed_id, results = process_image(file)
            if not all([original_id, processed_id, results]):
                raise Exception("Error al procesar la imagen")
            
            # Procesar detecciones
            detections = process_detections(results, original_id, session['user_id'])
            
            # Guardar en MongoDB la sesión de detección
            detection_session = {
                'user_id': session['user_id'],
                'original_image_id': original_id,
                'processed_image_id': processed_id,
                'timestamp': datetime.now(),
                'detections': detections
            }
            mongo_db.detection_sessions.insert_one(detection_session)
            
            return render_template('index.html',
                                image_id=processed_id,
                                original_id=original_id,
                                timestamp=datetime.now().timestamp(),
                                detections=detections,
                                username=session.get('username'))
                    
        except Exception as e:
            print(f"Error processing image: {str(e)}")
            return render_template('index.html', error=f"Error al procesar la imagen: {str(e)}")
    
    return render_template('index.html', username=session.get('username'))

@app.route('/file/<file_id>')
@login_required
def serve_file(file_id):
    """Sirve archivos desde MongoDB"""
    try:
        file_data = get_file_from_mongodb(file_id)
        if not file_data:
            raise Exception("Archivo no encontrado")
        
        return send_file(
            io.BytesIO(file_data.read()),
            mimetype='image/jpeg',
            as_attachment=False,
            download_name=file_data.filename
        )
    except Exception as e:
        return f"Error al recuperar archivo: {str(e)}", 404

@app.route('/detection/<int:detection_id>')
@login_required
def detection_detail(detection_id):
    # Obtener la detección de MySQL
    detection = Detection.query.get_or_404(detection_id)
    
    # Verificar permisos
    if detection.user_id != session['user_id']:
        flash('No tienes permiso para ver esta detección', 'error')
        return redirect(url_for('predict_img'))
    
    # Obtener metadata adicional de MongoDB
    try:
        metadata = mongo_db.detections_metadata.find_one({
            'mysql_detection_id': detection_id
        })
        
        # Obtener las imágenes asociadas
        original_id, processed_id = get_detection_images(detection_id)
        
        # Obtener las enfermedades asociadas
        diseases = DiseaseDetection.query.filter_by(detection_id=detection_id).all()
        
        # Preparar los datos de enfermedades
        diseases_data = []
        for disease in diseases:
            disease_info = DiseaseDescription.query.filter_by(name=disease.disease_name).first()
            
            disease_data = {
                'class': disease.disease_name,
                'confidence': disease.confidence,
                'disease_info': {
                    'short_description': disease_info.short_description if disease_info else "Información no disponible",
                    'cause': disease_info.cause if disease_info else "No especificada",
                    'effects': disease_info.effects if disease_info else "No especificados",
                    'recommendations': disease_info.recommendations if disease_info else "No especificadas",
                    'source': disease_info.source if disease_info else "Fuente desconocida"
                } if disease_info else None
            }
            diseases_data.append(disease_data)
        
        # Obtener usuario
        user = User.query.filter_by(id=detection.user_id).first()
        detection.username = user.username if user else 'Usuario'
        
        return render_template('detalle.html', 
                             detection=detection,
                             diseases=diseases_data,
                             original_id=original_id,
                             processed_id=processed_id,
                             metadata=metadata)
                             
    except Exception as e:
        print(f"Error al obtener detalles: {e}")
        flash('Error al cargar los detalles de la detección', 'error')
        return redirect(url_for('predict_img'))
@app.route('/process_frame', methods=['POST'])
@login_required
def process_frame():
    global model
    try:
        if model is None:
            if not load_model():
                return jsonify({
                    'status': 'error',
                    'message': 'Error al cargar el modelo'
                }), 500

        data = request.get_json()
        frame_data = data['frame']
        session_id = data.get('session_id')
        
        # Convertir frame
        frame_bytes = base64.b64decode(frame_data.split(',')[1])
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Generar nombre único para el frame
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        frame_filename = f"frame_{session_id}_{timestamp}.jpg"
        
        # Guardar frame en MongoDB
        _, frame_encoded = cv2.imencode('.jpg', frame)
        frame_id = save_file_to_mongodb(
            frame_encoded.tobytes(),
            frame_filename,
            'webcam_frame'
        )
        
        results = model(frame, save=False)
        
        detections = []
        confidence_sum = 0
        
        for result in results:
            for box in result.boxes:
                class_name = result.names[int(box.cls)]
                confidence = float(box.conf)
                xyxy = box.xyxy[0].tolist()
                
                if confidence > 0.5:
                    detections.append({
                        "class": class_name,
                        "confidence": confidence,
                        "bbox": xyxy
                    })
                    confidence_sum += confidence

        if session_id and detections:
            webcam_session = WebcamDetection.query.get(session_id)
            if webcam_session:
                webcam_session.total_frames += 1
                webcam_session.total_detections += len(detections)
                webcam_session.average_confidence = confidence_sum / len(detections)
                webcam_session.end_time = datetime.utcnow()
                
                # Guardar detecciones del frame en MongoDB
                frame_detection_data = {
                    'session_id': session_id,
                    'frame_id': frame_id,
                    'frame_number': webcam_session.total_frames,
                    'detections': detections,
                    'timestamp': datetime.utcnow(),
                    'user_id': session['user_id']
                }
                mongo_db.webcam_frame_detections.insert_one(frame_detection_data)
                
                # Mantener también el registro en MySQL para compatibilidad
                for detection in detections:
                    frame_detection = WebcamFrameDetection(
                        session_id=session_id,
                        frame_number=webcam_session.total_frames,
                        disease_name=detection["class"],
                        confidence=detection["confidence"],
                        frame_path=frame_id,  # Ahora guardamos el ID de MongoDB
                        user_id=session['user_id']
                    )
                    db.session.add(frame_detection)
                
                db.session.commit()
        
        return jsonify({
            'status': 'success',
            'detections': detections,
            'frame_id': frame_id
        })
        
    except Exception as e:
        print(f"Error processing frame: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/webcam/start_session', methods=['POST'])
@login_required
def start_webcam_session():
    try:
        stream_type = request.form.get('type', 'webcam')
        
        # Crear sesión en MySQL
        webcam_session = WebcamDetection(
            stream_type=stream_type,
            user_id=session['user_id']
        )
        db.session.add(webcam_session)
        db.session.commit()
        
        # Crear documento de sesión en MongoDB
        mongo_session = {
            'mysql_session_id': webcam_session.id,
            'stream_type': stream_type,
            'user_id': session['user_id'],
            'start_time': datetime.utcnow(),
            'frames': [],
            'status': 'active'
        }
        mongo_db.webcam_sessions.insert_one(mongo_session)
        
        return jsonify({'session_id': webcam_session.id})
        
    except Exception as e:
        print(f"Error starting webcam session: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/webcam/end_session', methods=['POST'])
@login_required
def end_webcam_session():
    try:
        session_id = request.form.get('session_id')
        webcam_session = WebcamDetection.query.get_or_404(session_id)
        
        if webcam_session.user_id != session['user_id']:
            abort(403)
        
        webcam_session.end_time = datetime.utcnow()
        db.session.commit()
        
        # Actualizar estado en MongoDB
        mongo_db.webcam_sessions.update_one(
            {'mysql_session_id': session_id},
            {
                '$set': {
                    'status': 'completed',
                    'end_time': datetime.utcnow(),
                    'total_frames': webcam_session.total_frames,
                    'total_detections': webcam_session.total_detections,
                    'average_confidence': webcam_session.average_confidence
                }
            }
        )
        
        return jsonify({
            'total_frames': webcam_session.total_frames,
            'total_detections': webcam_session.total_detections,
            'average_confidence': webcam_session.average_confidence
        })
        
    except Exception as e:
        print(f"Error ending webcam session: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
@app.route('/api/stats/general')
@login_required
def get_general_stats():
    user_id = session['user_id']
    try:
        # Estadísticas de MySQL
        mysql_stats = {
            'total_detections': Detection.query.filter_by(user_id=user_id).count(),
            'total_diseases': DiseaseDetection.query.filter_by(user_id=user_id).count(),
            'healthy_plants': Detection.query.filter_by(user_id=user_id, has_diseases=False).count(),
            'affected_plants': Detection.query.filter_by(user_id=user_id, has_diseases=True).count()
        }
        
        # Estadísticas adicionales de MongoDB
        mongo_stats = mongo_db.detections_metadata.aggregate([
            {'$match': {'user_id': user_id}},
            {'$group': {
                '_id': None,
                'total_files': {'$sum': 1},
                'avg_confidence': {'$avg': '$average_confidence'},
                'total_storage': {'$sum': '$file_size'},
            }}
        ]).next()
        
        stats = {**mysql_stats, **{
            'total_files': mongo_stats.get('total_files', 0),
            'avg_confidence': round(mongo_stats.get('avg_confidence', 0), 2),
            'storage_used_mb': round(mongo_stats.get('total_storage', 0) / (1024 * 1024), 2)
        }}
        
        return jsonify(stats)
    except Exception as e:
        print(f"Error obteniendo estadísticas: {e}")
        return jsonify(mysql_stats)

@app.route('/detection/<int:detection_id>/pdf')
@login_required
def detection_to_pdf(detection_id):
    try:
        # Obtener la detección
        detection = Detection.query.get_or_404(detection_id)

        if detection.user_id != session['user_id']:
            flash('No tienes permiso para descargar esta detección', 'error')
            return redirect(url_for('predict_img'))

        # Obtener imágenes de MongoDB
        original_id, processed_id = get_detection_images(detection_id)
        
        # Obtener metadata adicional
        metadata = mongo_db.detections_metadata.find_one({
            'mysql_detection_id': detection_id
        })

        # Obtener las enfermedades asociadas
        diseases = DiseaseDetection.query.filter_by(detection_id=detection_id).all()
        diseases_data = []
        
        for disease in diseases:
            disease_info = DiseaseDescription.query.filter_by(name=disease.disease_name).first()
            
            disease_data = {
                'class': disease.disease_name,
                'confidence': disease.confidence,
                'disease_info': {
                    'short_description': disease_info.short_description if disease_info else "Información no disponible",
                    'cause': disease_info.cause if disease_info else "No especificada",
                    'effects': disease_info.effects if disease_info else "No especificados",
                    'recommendations': disease_info.recommendations if disease_info else "No especificadas",
                    'source': disease_info.source if disease_info else "Fuente desconocida"
                } if disease_info else None
            }
            diseases_data.append(disease_data)

        # Renderizar HTML con las imágenes en base64
        if original_id:
            original_file = get_file_from_mongodb(original_id)
            original_base64 = base64.b64encode(original_file.read()).decode()
        else:
            original_base64 = None

        if processed_id:
            processed_file = get_file_from_mongodb(processed_id)
            processed_base64 = base64.b64encode(processed_file.read()).decode()
        else:
            processed_base64 = None

        rendered_html = render_template(
            'pdf_template.html', 
            detection=detection, 
            diseases=diseases_data,
            original_image=original_base64,
            processed_image=processed_base64,
            metadata=metadata,
            logo_url=url_for('static', filename='assets/images/logo_nawicrop.png')
        )

        # Crear PDF
        pdf = io.BytesIO()
        pisa.CreatePDF(io.StringIO(rendered_html), dest=pdf)
        pdf.seek(0)

        response = make_response(pdf.read())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=deteccion_{detection_id}.pdf'
        return response
        
    except Exception as e:
        print(f"Error generando PDF: {e}")
        flash('Error al generar el PDF', 'error')
        return redirect(url_for('detection_detail', detection_id=detection_id))

@app.route('/cleanup')
@login_required
def cleanup_old_files():
    """Limpia archivos antiguos de MongoDB"""
    try:
        # Solo usuarios autorizados pueden ejecutar la limpieza
        if not session.get('is_admin'):
            abort(403)
            
        cutoff_date = datetime.now() - timedelta(days=30)
        
        # Encontrar archivos antiguos
        old_files = mongo_db.fs.files.find({
            "uploadDate": {"$lt": cutoff_date}
        })
        
        deleted_count = 0
        for file in old_files:
            fs.delete(file._id)
            deleted_count += 1
            
        # Limpiar registros huérfanos
        mongo_db.detections_metadata.delete_many({
            "timestamp": {"$lt": cutoff_date}
        })
        
        return jsonify({
            'status': 'success',
            'deleted_files': deleted_count
        })
        
    except Exception as e:
        print(f"Error en limpieza: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Función de utilidad para la gestión de errores
@app.errorhandler(Exception)
def handle_error(error):
    print(f"Error: {str(error)}")
    if isinstance(error, HTTPException):
        return render_template('error.html', error=error), error.code
    return render_template('error.html', error=str(error)), 500
# Configuraciones adicionales para MongoDB
def init_mongodb():
    """Inicializa las colecciones y índices necesarios en MongoDB"""
    try:
        # Crear índices para mejorar el rendimiento
        mongo_db.fs.files.create_index("uploadDate")
        mongo_db.detections_metadata.create_index("mysql_detection_id")
        mongo_db.detections_metadata.create_index("user_id")
        mongo_db.webcam_sessions.create_index("mysql_session_id")
        mongo_db.webcam_frame_detections.create_index([
            ("session_id", 1),
            ("frame_number", 1)
        ])
        
        # Crear colección de configuración si no existe
        if 'config' not in mongo_db.list_collection_names():
            mongo_db.config.insert_one({
                'version': '1.0',
                'initialized_date': datetime.now(),
                'storage_limit_mb': 5000,
                'file_retention_days': 30
            })
        
        print("✅ MongoDB inicializado correctamente")
        return True
    except Exception as e:
        print(f"❌ Error inicializando MongoDB: {e}")
        return False

def check_storage_limits():
    """Verifica y gestiona límites de almacenamiento"""
    try:
        total_size = 0
        for file in mongo_db.fs.files.find():
            total_size += file.get('length', 0)
        
        total_size_mb = total_size / (1024 * 1024)
        config = mongo_db.config.find_one()
        
        if total_size_mb > config['storage_limit_mb']:
            # Eliminar archivos más antiguos
            old_files = mongo_db.fs.files.find().sort('uploadDate', 1).limit(10)
            for file in old_files:
                fs.delete(file._id)
                
        return True
    except Exception as e:
        print(f"Error checking storage limits: {e}")
        return False

# Configuraciones de seguridad adicionales
@app.before_request
def before_request():
    """Verificaciones antes de cada request"""
    try:
        if request.endpoint and 'static' not in request.endpoint:
            # Verificar límites de almacenamiento periódicamente
            if random.random() < 0.1:  # 10% de las requests
                check_storage_limits()
            
            # Verificar sesión MongoDB si está autenticado
            if 'user_id' in session:
                mongo_db.active_sessions.update_one(
                    {'user_id': session['user_id']},
                    {
                        '$set': {
                            'last_active': datetime.now(),
                            'user_agent': request.headers.get('User-Agent')
                        }
                    },
                    upsert=True
                )
    except Exception as e:
        print(f"Error in before_request: {e}")

@app.after_request
def after_request(response):
    """Procedimientos después de cada request"""
    try:
        # Limpiar archivos temporales si existen
        if hasattr(g, 'temp_files'):
            for temp_file in g.temp_files:
                try:
                    os.remove(temp_file)
                except:
                    pass
    except Exception as e:
        print(f"Error in after_request: {e}")
    return response

# Inicialización de la aplicación
if __name__ == "__main__":
    with app.app_context():
        # Inicializar bases de datos
        db.create_all()  # MySQL
        init_mongodb()   # MongoDB
        
        # Cargar el modelo
        if not load_model():
            print("⚠️ Error al cargar el modelo YOLO")
            sys.exit(1)
        
        # Verificar conexiones
        try:
            # Verificar MySQL
            db.session.execute('SELECT 1')
            print("✅ Conexión MySQL exitosa")
            
            # Verificar MongoDB
            mongo_client.admin.command('ping')
            print("✅ Conexión MongoDB exitosa")
            
            # Configurar colecciones necesarias
            required_collections = [
                'detections_metadata',
                'webcam_sessions',
                'webcam_frame_detections',
                'image_relations',
                'active_sessions',
                'config'
            ]
            
            existing_collections = mongo_db.list_collection_names()
            for collection in required_collections:
                if collection not in existing_collections:
                    mongo_db.create_collection(collection)
                    print(f"✅ Colección {collection} creada")
            
        except Exception as e:
            print(f"❌ Error en verificación de conexiones: {e}")
            sys.exit(1)
    
    # Configurar y ejecutar la aplicación
    parser = argparse.ArgumentParser(description="Flask app con YOLO y MongoDB")
    parser.add_argument("--port", default=5000, type=int, help="puerto para el servidor")
    parser.add_argument("--debug", action="store_true", help="ejecutar en modo debug")
    args = parser.parse_args()
    
    # Ejecutar la aplicación
    app.run(
        host="0.0.0.0",
        port=args.port,
        debug=args.debug
    )            
