from flask import Flask, render_template, request, redirect, send_file, url_for, Response, send_from_directory, jsonify, flash, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from ultralytics import YOLO
from datetime import datetime
import argparse
import io
import json
import os
import shutil
import time
from PIL import Image
import cv2
import numpy as np
import pymysql
from functools import wraps
from models import db, Detection, DiseaseDetection, User, WebcamDetection, WebcamFrameDetection, DiseaseDescription
from flask import render_template, request, redirect, url_for, flash, session, make_response
from xhtml2pdf import pisa
import io
import base64
from flask import abort
import requests
import tempfile
import os

import cloudinary
import cloudinary.uploader
import cloudinary.api

# Configuración de Cloudinary con tus credenciales
cloudinary.config(
    cloud_name="dxrt7dr1v",  # Cambia por tu "Cloud Name"
    api_key="457733397447258",  # Cambia por tu "API Key"
    api_secret="Y8EFVvYGT-5mXX-Jicfv_2tYQmM"  # Cambia por tu "API Secret"
)
model = None

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

# Registrar PyMySQL como el controlador de MySQL
pymysql.install_as_MySQLdb()

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_muy_segura'  # Cambiar en producción




# Configuración
UPLOAD_FOLDER = 'uploads'
PREDICT_FOLDER = 'runs/detect/predict'
JS_FOLDER = 'static/assets/js'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Configuración de la base de datos para Railway
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:DAcnRAsSqsdiVCpYmgydAIbsnpsTTeBN@autorack.proxy.rlwy.net:27853/railway'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar la base de datos con la app
db.init_app(app)
# Al inicio de tu aplicación, después de definir las constantes
def ensure_directories():
    """Asegura que existan todos los directorios necesarios"""
    directories = [
        UPLOAD_FOLDER,
        os.path.join(UPLOAD_FOLDER, 'temp'),
        'runs',
        'runs/detect',
        JS_FOLDER
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

# Llamar a esta función al iniciar la aplicación
with app.app_context():
    ensure_directories()
    db.create_all()
    load_model()

# Función para reiniciar la base de datos
def reset_database():
    with app.app_context():
        # Eliminar todas las tablas existentes
        db.drop_all()
        # Crear todas las tablas nuevamente
        db.create_all()
        # Crear un usuario por defecto si es necesario
        default_user = User(
            username="admin",
            email="admin@example.com",
            password=generate_password_hash("admin123")
        )
        try:
            db.session.add(default_user)
            db.session.commit()
            print("Base de datos reiniciada exitosamente")
        except Exception as e:
            db.session.rollback()
            print(f"Error al crear usuario por defecto: {e}")
            

# Crear directorios necesarios
for directory in [UPLOAD_FOLDER, PREDICT_FOLDER, JS_FOLDER]:
    if not os.path.exists(directory):
        os.makedirs(directory)
        

# Decorador para requerir login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder a esta página', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_detections(results, image_path, user_id, original_url=None, processed_url=None):
    """Procesa las detecciones y guarda en la base de datos"""
    detections = []
    diseases_detected = []
    
    # Crear registro principal de detección
    detection_record = Detection(
        image_path=image_path,
        image_original_url=original_url,
        image_processed_url=processed_url,
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
            
            try:
                disease_info = DiseaseDescription.query.filter(
                    DiseaseDescription.name.strip() == class_name.strip()
                ).first()
                
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
                    
            except Exception as e:
                print(f"Error procesando detección: {str(e)}")
                continue
    
    detection_record.diseases_detected = ','.join(diseases_detected) if diseases_detected else ''
    db.session.commit()
    return detections
# Ruta principal - Landing page
@app.route('/')
def page():
    # Si el usuario ya está logueado, redirigir a index
    if 'user_id' in session:
        return redirect(url_for('predict_img'))
    return render_template('page.html')

# Ruta de login
@app.cli.command("reset-db")
def reset_db_command():
    """Resetea la base de datos de Railway."""
    import click
    
    if click.confirm('⚠️  ¿Estás seguro? Esto eliminará TODOS los datos existentes en Railway', abort=True):
        from migrate_db import reset_database
        if reset_database():
            click.echo('✅ Base de datos reiniciada exitosamente')
        else:
            click.echo('❌ Error al resetear la base de datos')

@app.route('/login', methods=['GET', 'POST'])
def login():
    print("Accediendo a la ruta de login")  # Log inicial
    
    # Si el usuario ya está logueado, redirigir a index
    if 'user_id' in session:
        print(f"Usuario ya en sesión: {session['user_id']}")  # Log de sesión existente
        return redirect(url_for('predict_img'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        print(f"Intento de login para usuario: {username}")  # Log de intento de login
        
        user = User.query.filter_by(username=username).first()
        
        if user:
            print(f"Usuario encontrado: {user.id}")  # Log usuario encontrado
            if check_password_hash(user.password, password):
                print("Contraseña correcta")  # Log contraseña correcta
                session['user_id'] = user.id
                session['username'] = user.username
                flash('Inicio de sesión exitoso!', 'success')
                print("Sesión iniciada, redirigiendo a predict_img")  # Log sesión iniciada
                return redirect(url_for('predict_img'))
            else:
                print("Contraseña incorrecta")  # Log contraseña incorrecta
                flash('Usuario o contraseña incorrectos', 'error')
        else:
            print("Usuario no encontrado")  # Log usuario no encontrado
            flash('Usuario o contraseña incorrectos', 'error')
        
        return render_template('login.html')
    
    print("Renderizando página de login")  # Log renderizado de página
    return render_template('login.html')

# Ruta de registro
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('El nombre de usuario ya está registrado', 'error')
            return redirect(url_for('login'))
            
        if User.query.filter_by(email=email).first():
            flash('El email ya está registrado', 'error')
            return redirect(url_for('login'))
        
        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username,
            email=email,
            password=hashed_password
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registro exitoso! Por favor inicia sesión', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('Error en el registro', 'error')
            return redirect(url_for('login'))
    
    return redirect(url_for('login'))

# Ruta de logout
@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión exitosamente', 'success')
    return redirect(url_for('login'))

# Ruta principal después del login - Index/Dashboard
@app.route("/index", methods=["GET", "POST"])
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
            # Crear directorios necesarios
            temp_dir = os.path.join(UPLOAD_FOLDER, 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            os.makedirs('runs/detect', exist_ok=True)
            
            # Guardar archivo temporalmente
            filename = secure_filename(file.filename)
            filepath = os.path.join(temp_dir, filename)
            file.save(filepath)
            
            # Convertir PNG a JPG si es necesario
            if filename.lower().endswith('.png'):
                img = cv2.imread(filepath)
                if img is None:
                    return render_template('index.html', error="Error al leer la imagen PNG")
                jpg_path = os.path.splitext(filepath)[0] + '.jpg'
                cv2.imwrite(jpg_path, img)
                os.remove(filepath)
                filepath = jpg_path
                filename = os.path.basename(filepath)
            
            # Cargar modelo
            global model
            if model is None:
                try:
                    print("Descargando modelo desde HuggingFace...")
                    model_url = "https://huggingface.co/javier233455/fresas/resolve/main/modelo1.pt"
                    model_path = os.path.join(tempfile.gettempdir(), 'modelo1.pt')
                    
                    if not os.path.exists(model_path):
                        response = requests.get(model_url, stream=True)
                        response.raise_for_status()
                        with open(model_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                    model = YOLO(model_path)
                except Exception as e:
                    print(f"Error al cargar el modelo: {str(e)}")
                    return render_template('index.html', error="Error al cargar el modelo de detección")
            
            # Subir imagen original a Cloudinary
            timestamp = int(time.time())
            try:
                upload_result = cloudinary.uploader.upload(
                    filepath,
                    public_id=f"uploads/originals/{os.path.splitext(filename)[0]}_{timestamp}",
                    folder="uploads/originals",
                    overwrite=True
                )
                original_url = upload_result['secure_url']
                original_public_id = upload_result['public_id']
                print(f"Imagen original subida a Cloudinary: {original_url}")
            except Exception as e:
                print(f"Error al subir imagen original: {str(e)}")
                return render_template('index.html', error="Error al subir la imagen original")
            
            # Realizar predicción
            try:
                results = model.predict(filepath, save=True)
                print("Predicción realizada exitosamente")
            except Exception as e:
                print(f"Error en predicción: {str(e)}")
                return render_template('index.html', error="Error al procesar la imagen")
            
            # Encontrar y subir imagen procesada
            processed_url = None
            processed_public_id = None
            try:
                # Encontrar la carpeta más reciente de predicciones
                predict_dir = "runs/detect"
                predict_folders = [d for d in os.listdir(predict_dir) if d.startswith('predict')]
                if predict_folders:
                    latest_folder = max(predict_folders, key=lambda x: os.path.getctime(os.path.join(predict_dir, x)))
                    processed_path = os.path.join(predict_dir, latest_folder, filename)
                    
                    if os.path.exists(processed_path):
                        # Subir imagen procesada a Cloudinary
                        upload_result = cloudinary.uploader.upload(
                            processed_path,
                            public_id=f"processed/detections/{os.path.splitext(filename)[0]}_{timestamp}",
                            folder="processed/detections",
                            overwrite=True
                        )
                        processed_url = upload_result['secure_url']
                        processed_public_id = upload_result['public_id']
                        print(f"Imagen procesada subida a Cloudinary: {processed_url}")
            except Exception as e:
                print(f"Error al subir imagen procesada: {str(e)}")
            
            # Procesar detecciones y guardar en BD
            try:
                # Crear registro de detección
                detection = Detection(
                    image_original_url=original_url,
                    image_processed_url=processed_url,
                    cloudinary_public_id=original_public_id,
                    user_id=session['user_id']
                )
                db.session.add(detection)
                db.session.commit()
                
                # Procesar detecciones individuales
                detections_data = []
                for result in results:
                    for box in result.boxes:
                        class_name = result.names[int(box.cls)]
                        confidence = float(box.conf)
                        
                        # Crear registro de detección de enfermedad
                        disease_detection = DiseaseDetection(
                            detection_id=detection.id,
                            disease_name=class_name,
                            confidence=confidence,
                            user_id=session['user_id']
                        )
                        db.session.add(disease_detection)
                        
                        detections_data.append({
                            "class": class_name,
                            "confidence": confidence
                        })
                
                detection.total_detections = len(detections_data)
                detection.has_diseases = any(d["class"].lower() != "sana" for d in detections_data)
                detection.diseases_detected = ",".join(set(d["class"] for d in detections_data))
                db.session.commit()
                
            except Exception as e:
                db.session.rollback()
                print(f"Error al guardar en BD: {str(e)}")
                return render_template('index.html', error="Error al guardar detecciones")
            
            # Limpiar archivos temporales
            try:
                os.remove(filepath)
                shutil.rmtree(os.path.join("runs", "detect"), ignore_errors=True)
            except Exception as e:
                print(f"Error limpiando archivos: {str(e)}")
            
            # Generar archivo JS
            try:
                js_dir = os.path.join(app.root_path, JS_FOLDER)
                os.makedirs(js_dir, exist_ok=True)
                with open(os.path.join(js_dir, 'detections.js'), 'w', encoding='utf-8') as f:
                    f.write(f'const detections = {json.dumps(detections_data, indent=2)};')
            except Exception as e:
                print(f"Error generando JS: {str(e)}")
            
            return render_template('index.html',
                               original_url=original_url,
                               processed_url=processed_url,
                               detections=detections_data,
                               timestamp=datetime.now().timestamp(),
                               username=session.get('username'))
            
        except Exception as e:
            print(f"Error general: {str(e)}")
            return render_template('index.html', error=f"Error en el procesamiento: {str(e)}")
        
    return render_template('index.html', username=session.get('username'))

# Nueva función para subir imágenes a Cloudinary

def subir_imagen_a_cloudinary(filepath, folder_name="default"):
    """
    Sube una imagen a Cloudinary en la carpeta especificada
    """
    try:
        # Agregar timestamp al nombre para evitar colisiones
        timestamp = int(time.time())
        public_id = f"{folder_name}/{os.path.splitext(os.path.basename(filepath))[0]}_{timestamp}"
        
        respuesta = cloudinary.uploader.upload(
            filepath,
            public_id=public_id,
            folder=folder_name,
            overwrite=True
        )
        print(f"Imagen subida exitosamente a Cloudinary en {folder_name}")
        return respuesta['secure_url']
    except Exception as e:
        print(f"Error al subir la imagen a Cloudinary: {str(e)}")
        return None
    
def guardar_deteccion_cloudinary(imagen_original, imagen_procesada):
    """
    Guarda tanto la imagen original como la procesada en Cloudinary
    """
    try:
        # Subir imagen original
        url_original = subir_imagen_a_cloudinary(
            imagen_original, 
            folder_name="uploads/originals"
        )
        
        # Subir imagen procesada
        url_procesada = subir_imagen_a_cloudinary(
            imagen_procesada, 
            folder_name="detections/processed"
        )
        
        return url_original, url_procesada
    except Exception as e:
        print(f"Error al guardar las imágenes en Cloudinary: {str(e)}")
        return None, None




@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=session.get('username'))

@app.route('/detection/<int:detection_id>')
@login_required
def detection_detail(detection_id):
    # Obtener la detección
    detection = Detection.query.get_or_404(detection_id)
    
    
    # Verificar que el usuario actual sea el dueño de la detección
    if detection.user_id != session['user_id']:
        flash('No tienes permiso para ver esta detección', 'error')
        return redirect(url_for('predict_img'))
    
    # Obtener las enfermedades asociadas a la detección
    diseases = DiseaseDetection.query.filter_by(detection_id=detection_id).all()
    
    # Preparar los datos detallados de las enfermedades
    diseases_data = []
    for disease in diseases:
        # Obtener información detallada desde DiseaseDescription
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
    
    # Obtener el usuario relacionado con la detección
    user = User.query.filter_by(id=detection.user_id).first()
    detection.username = user.username if user else 'Usuario'
    
    # Renderizar la plantilla con los datos
    return render_template('detalle.html', 
                           detection=detection,
                           diseases=diseases_data)
@app.route('/detection/<int:detection_id>/pdf')
@login_required
def detection_to_pdf(detection_id):
    # Obtener la detección
    detection = Detection.query.get_or_404(detection_id)

    # Verificar que el usuario actual sea el dueño de la detección
    if detection.user_id != session['user_id']:
        flash('No tienes permiso para descargar esta detección', 'error')
        return redirect(url_for('predict_img'))

    # Obtener las enfermedades asociadas
    diseases = DiseaseDetection.query.filter_by(detection_id=detection_id).all()

    # Preparar los datos de enfermedades
    diseases_data = []
    for disease in diseases:
        # Obtener información detallada desde DiseaseDescription
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

    # Renderizar la plantilla en HTML
    rendered_html = render_template(
        'pdf_template.html', 
        detection=detection, 
        diseases=diseases_data,
        logo_url=url_for('static', filename='assets/images/logo_nawicrop.png')  # Ruta al logo
    )

    # Crear un archivo PDF en memoria
    pdf = io.BytesIO()
    pisa.CreatePDF(io.StringIO(rendered_html), dest=pdf)
    pdf.seek(0)

    # Enviar el PDF como respuesta al cliente
    response = make_response(pdf.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=deteccion_{detection_id}.pdf'
    return response

@app.route('/profile')
@login_required
def profile():
    user = User.query.filter_by(id=session['user_id']).first()
    if user is None:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('logout'))
        
    total_detections = Detection.query.filter_by(user_id=user.id).count()
    total_diseases = DiseaseDetection.query.filter_by(user_id=user.id).count()
    recent_detections = Detection.query.filter_by(user_id=user.id).order_by(Detection.timestamp.desc()).limit(5).all()
    
    return render_template('profile.html', 
                         user=user, 
                         total_detections=total_detections,
                         total_diseases=total_diseases,
                         recent_detections=recent_detections)

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    user = User.query.filter_by(id=session['user_id']).first()
    if user is None:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('logout'))
    
    if request.form.get('username'):
        existing_user = User.query.filter_by(username=request.form.get('username')).first()
        if existing_user and existing_user.id != user.id:
            flash('El nombre de usuario ya está en uso', 'error')
            return redirect(url_for('profile'))
        user.username = request.form.get('username')
        session['username'] = user.username
    
    if request.form.get('email'):
        existing_user = User.query.filter_by(email=request.form.get('email')).first()
        if existing_user and existing_user.id != user.id:
            flash('El email ya está en uso', 'error')
            return redirect(url_for('profile'))
        user.email = request.form.get('email')
    
    if request.form.get('password'):
        user.password = generate_password_hash(request.form.get('password'))
    
    try:
        db.session.commit()
        flash('Perfil actualizado exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al actualizar el perfil: ' + str(e), 'error')
    
    return redirect(url_for('profile'))

@app.route('/settings')
@login_required
def settings():
    user = User.query.filter_by(id=session['user_id']).first()
    if user is None:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('logout'))
        
    user_settings = {
        'theme': user.theme or 'light',
        'font_size': user.font_size or 'medium',
        'email_notifications': user.email_notifications or False,
        'summary_frequency': user.summary_frequency or 'daily',
        'confidence_threshold': user.confidence_threshold or 50,
        'auto_save': user.auto_save or True,
        'export_format': user.export_format or 'pdf',
        'include_images': user.include_images or True
    }
    return render_template('settings.html', user=user, settings=user_settings)

@app.route('/update_appearance', methods=['POST'])
@login_required
def update_appearance():
    user = User.query.filter_by(id=session['user_id']).first()
    if user is None:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('logout'))
    
    try:
        user.theme = request.form.get('theme', 'light')
        user.font_size = request.form.get('font_size', 'medium')
        db.session.commit()
        flash('Configuración de apariencia actualizada', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar la configuración: {str(e)}', 'error')
    return redirect(url_for('settings'))

@app.route('/update_notifications', methods=['POST'])
@login_required
def update_notifications():
    user = User.query.filter_by(id=session['user_id']).first()
    
    if user is None:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('logout'))
    
    try:
        user.email_notifications = 'email_notifications' in request.form
        user.summary_frequency = request.form.get('summary_frequency', 'daily')
        db.session.commit()
        flash('Configuración de notificaciones actualizada', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar la configuración: {str(e)}', 'error')
    
    return redirect(url_for('settings'))

@app.route('/update_detection_settings', methods=['POST'])
@login_required
def update_detection_settings():
    user = User.query.filter_by(id=session['user_id']).first()
    if user is None:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('logout'))
    
    try:
        user.confidence_threshold = int(request.form.get('confidence_threshold', 50))
        user.auto_save = 'auto_save' in request.form
        db.session.commit()
        flash('Configuración de detección actualizada', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar la configuración: {str(e)}', 'error')
    return redirect(url_for('settings'))

@app.route('/update_export_settings', methods=['POST'])
@login_required
def update_export_settings():
    user = User.query.filter_by(id=session['user_id']).first()
    if user is None:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('logout'))
    
    try:
        user.export_format = request.form.get('export_format', 'pdf')
        user.include_images = 'include_images' in request.form
        db.session.commit()
        flash('Preferencias de exportación actualizadas', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar la configuración: {str(e)}', 'error')
    return redirect(url_for('settings'))

@app.route('/api/stats/general')
@login_required
def get_general_stats():
    user_id = session['user_id']
    stats = {
        'total_detections': Detection.query.filter_by(user_id=user_id).count(),
        'total_diseases': DiseaseDetection.query.filter_by(user_id=user_id).count(),
        'healthy_plants': Detection.query.filter_by(user_id=user_id, has_diseases=False).count(),
        'affected_plants': Detection.query.filter_by(user_id=user_id, has_diseases=True).count()
    }
    return jsonify(stats)

@app.route('/detections')
@login_required
def detections_list():
    detections = Detection.query.filter_by(user_id=session['user_id']).order_by(Detection.timestamp.desc()).all()
    
    # Obtener enfermedades para cada detección
    for detection in detections:
        diseases = DiseaseDetection.query.filter_by(detection_id=detection.id).all()
        detection.diseases_list = [disease.disease_name for disease in diseases]
    
    return render_template('detections_list.html', detections=detections)

@app.route('/uploads/<path:filename>')
@login_required
def uploads(filename):
    return send_from_directory('uploads', filename)

@app.route('/api/stats/diseases')
@login_required
def get_disease_stats():
    user_id = session['user_id']
    user = User.query.filter_by(id=user_id).first()
    diseases = DiseaseDetection.query.filter_by(user_id=user_id).all()
    stats = {}
    
    for disease in diseases:
        if disease.disease_name not in stats:
            stats[disease.disease_name] = {
                'total': 0,
                'avg_confidence': 0,
                'detections': [],
                'username': user.username  # Añadir nombre de usuario
            }
        
        stats[disease.disease_name]['total'] += 1
        stats[disease.disease_name]['detections'].append({
            'confidence': disease.confidence,
            'date': disease.detection_date.isoformat()
        })
    
    for disease_name in stats:
        confidences = [d['confidence'] for d in stats[disease_name]['detections']]
        stats[disease_name]['avg_confidence'] = sum(confidences) / len(confidences)
    
    return jsonify(stats)

@app.route('/api/detections/history')
@login_required
def get_detection_history():
    user_id = session['user_id']
    user = User.query.filter_by(id=user_id).first()
    detections = Detection.query.filter_by(user_id=user_id).order_by(Detection.timestamp.desc()).limit(30).all()
    
    history = []
    for detection in detections:
        # Obtener las enfermedades asociadas a esta detección
        diseases = DiseaseDetection.query.filter_by(detection_id=detection.id).all()
        disease_names = [disease.disease_name for disease in diseases]
        
        history.append({
            'date': detection.timestamp.isoformat(),
            'total': detection.total_detections,
            'has_diseases': detection.has_diseases,
            'diseases': disease_names,  # Lista de enfermedades detectadas
            'username': user.username  # Nombre del usuario
        })
    
    return jsonify(history)
# Modificar la ruta de procesamiento de frames de webcam
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
        temp_frame_path = os.path.join(UPLOAD_FOLDER, 'temp', frame_filename)
        
        # Crear directorio temporal si no existe
        os.makedirs(os.path.dirname(temp_frame_path), exist_ok=True)
        
        # Guardar frame temporalmente
        cv2.imwrite(temp_frame_path, frame)
        
        # Realizar detección
        results = model(frame, save=True)
        
        # Procesar resultados
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
        
        # Subir frame original y procesado a Cloudinary
        if detections:
            # Obtener frame procesado
            processed_frame_path = os.path.join("runs", "detect", "predict", frame_filename)
            
            # Subir a Cloudinary
            url_original = subir_imagen_a_cloudinary(
                temp_frame_path, 
                folder_name="webcam/originals"
            )
            
            url_procesada = subir_imagen_a_cloudinary(
                processed_frame_path, 
                folder_name="webcam/detections"
            )
            
            # Guardar en la base de datos
            if session_id and url_original and url_procesada:
                webcam_session = WebcamDetection.query.get(session_id)
                if webcam_session:
                    webcam_session.total_frames += 1
                    webcam_session.total_detections += len(detections)
                    webcam_session.average_confidence = confidence_sum / len(detections)
                    
                    frame_detection = WebcamFrameDetection(
                        session_id=session_id,
                        frame_number=webcam_session.total_frames,
                        frame_original_url=url_original,
                        frame_processed_url=url_procesada,
                        user_id=session['user_id']
                    )
                    db.session.add(frame_detection)
                    db.session.commit()
        
        # Limpiar archivos temporales
        os.remove(temp_frame_path)
        if os.path.exists(processed_frame_path):
            os.remove(processed_frame_path)
        
        return jsonify({
            'status': 'success',
            'detections': detections,
            'original_url': url_original if 'url_original' in locals() else None,
            'processed_url': url_procesada if 'url_procesada' in locals() else None
        })
        
    except Exception as e:
        print(f"Error processing frame: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    
@app.route('/webcam_feed')
@login_required
def webcam_feed():
    model = YOLO('Modelo1.pt')  # Verificar que el modelo existe
    if not os.path.exists('Modelo1.pt'):
        flash('Modelo no encontrado', 'error')
        return redirect(url_for('predict_img'))
    return render_template('webcam.html', username=session.get('username'))

@app.route('/check_camera')
@login_required
def check_camera():
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return jsonify({'status': 'error', 'message': 'No se detectó ninguna cámara'})
        cap.release()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/rtsp_feed')
@login_required
def rtsp_feed():
    return render_template('rtsp.html', username=session.get('username'))

@app.route('/api/webcam/start_session', methods=['POST'])
@login_required
def start_webcam_session():
    stream_type = request.form.get('type', 'webcam')
    
    webcam_session = WebcamDetection(
        stream_type=stream_type,
        user_id=session['user_id']  # Aquí, 'session' se refiere a la sesión de Flask
    )
    
    db.session.add(webcam_session)
    db.session.commit()
    
    return jsonify({'session_id': webcam_session.id})

@app.route('/api/webcam/save_detection', methods=['POST'])
@login_required
def save_webcam_detection():
    data = request.get_json()
    
    frame_detection = WebcamFrameDetection(
        session_id=data['session_id'],
        frame_number=data['frame_number'],
        disease_name=data['disease_name'],
        confidence=data['confidence'],
        frame_path=data.get('frame_path'),
        user_id=session['user_id']
    )
    
    db.session.add(frame_detection)
    db.session.commit()
    
    return jsonify({'status': 'success'})

@app.route('/api/webcam/end_session', methods=['POST'])
@login_required
def end_webcam_session():
    session_id = request.form.get('session_id')
    webcam_session = WebcamDetection.query.get_or_404(session_id)
    
    if webcam_session.user_id != session['user_id']:
        abort(403)
    
    webcam_session.end_time = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'total_frames': webcam_session.total_frames,
        'total_detections': webcam_session.total_detections,
        'average_confidence': webcam_session.average_confidence
    })
@app.route('/test_webcam_detection')
def test_webcam_detection():
    try:
        test_session = WebcamDetection(
            stream_type='webcam',
            user_id=1
        )
        db.session.add(test_session)
        db.session.commit()
        return "WebcamDetection guardado correctamente"
    except Exception as e:
        return f"Error: {e}"


@app.route('/detect/<path:filename>')
@login_required
def detect(filename):
    return send_from_directory(PREDICT_FOLDER, filename)

@app.errorhandler(404)
def not_found_error(error):
    if request.path.startswith('/static/'):
        return '', 404
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        load_model()  # Cargar el modelo al iniciar
    
    # Ajusta el puerto dinámico para Render
    port = int(os.environ.get("PORT", 5000))  # Usa el puerto asignado por Render o 5000 por defecto
    app.run(host="0.0.0.0", port=port, debug=True)
