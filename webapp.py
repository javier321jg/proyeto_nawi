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
model = None

def load_model():
    global model
    try:
        model = YOLO('Modelo1.pt')
        print("Modelo YOLO cargado exitosamente")
        return True
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

# Configuración de la base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/fresas'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar la base de datos con la app
db.init_app(app)

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

def process_detections(results, image_path, user_id):
    """Procesa las detecciones y guarda en la base de datos"""
    detections = []
    diseases_detected = []
    
    # Crear registro principal de detección
    detection_record = Detection(
        image_path=image_path,
        total_detections=len(results[0].boxes),
        has_diseases=False,
        user_id=user_id
    )
    db.session.add(detection_record)
    db.session.commit()
    
    print("Procesando detecciones...")  # Log adicional
    
    for result in results:
        for box in result.boxes:
            class_name = result.names[int(box.cls)]
            confidence = float(box.conf)
            
            # Logs detallados para debugging
            print(f"Clase detectada: {class_name}")
            print(f"Formato de clase: {type(class_name)}")  # Ver el tipo de dato
            print(f"Longitud del nombre: {len(class_name)}")  # Ver si hay espacios extra
            
            # Intentar encontrar la enfermedad en la base de datos
            try:
                print(f"Buscando en BD: '{class_name}'")
                # Primero buscar exactamente como viene
                disease_info = DiseaseDescription.query.filter_by(name=class_name).first()
                
                if disease_info is None:
                    # Si no se encuentra, intentar con trim()
                    print("No se encontró con búsqueda exacta, intentando con trim()")
                    disease_info = DiseaseDescription.query.filter(
                        DiseaseDescription.name.strip() == class_name.strip()
                    ).first()
                
                print(f"Resultado de búsqueda: {disease_info}")
                
                # Si aún no se encuentra, mostrar todas las enfermedades disponibles
                if disease_info is None:
                    print("Enfermedades disponibles en BD:")
                    all_diseases = DiseaseDescription.query.all()
                    for disease in all_diseases:
                        print(f"- '{disease.name}' (longitud: {len(disease.name)})")
                
            except Exception as e:
                print(f"Error al buscar en la BD: {str(e)}")
                disease_info = None
            
            detection = {
                "class": class_name,
                "confidence": confidence
            }
            
            if disease_info:
                print(f"Agregando información de enfermedad para {class_name}")
                detection["disease_info"] = {
                    "short_description": disease_info.short_description,
                    "cause": disease_info.cause,
                    "effects": disease_info.effects,
                    "source": disease_info.source,
                    "recommendations": disease_info.recommendations  # Agregar recomendaciones
                }
            else:
                print(f"No se encontró información para {class_name}")
            
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
    return detections
# Ruta principal - Landing page
@app.route('/')
def page():
    # Si el usuario ya está logueado, redirigir a index
    if 'user_id' in session:
        return redirect(url_for('predict_img'))
    return render_template('page.html')

# Ruta de login
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
    print("Accediendo a predict_img")  # Log de acceso
    print(f"Sesión actual: {session}")  # Log de sesión
    if request.method == "POST":
        
        if 'file' not in request.files:
            return render_template('index.html', error="No se ha enviado ningún archivo")
        
        file = request.files['file']
        if file.filename == '':
            return render_template('index.html', error="No se ha seleccionado ningún archivo")
        
        if not allowed_file(file.filename):
            return render_template('index.html', error="Tipo de archivo no permitido")
        
        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            if filename.lower().endswith('.png'):
                img = cv2.imread(filepath)
                if img is None:
                    return render_template('index.html', error="Error al leer la imagen PNG")
                jpg_path = os.path.splitext(filepath)[0] + '.jpg'
                cv2.imwrite(jpg_path, img)
                filepath = jpg_path
                filename = os.path.basename(filepath)
            
            model = YOLO('Modelo1.pt')
            results = model.predict(filepath, save=True)
            
            detections = process_detections(results, filename, session['user_id'])
            
            js_dir = os.path.join(app.root_path, JS_FOLDER)
            os.makedirs(js_dir, exist_ok=True)
            
            with open(os.path.join(js_dir, 'detections.js'), 'w', encoding='utf-8') as f:
                f.write(f'const detections = {json.dumps(detections, indent=2)};')
            
            detect_dir = os.path.join(app.root_path, 'runs/detect')
            predict_folders = [d for d in os.listdir(detect_dir) if d.startswith('predict')]
            if not predict_folders:
                return render_template('index.html', error="No se encontraron resultados de la detección")
            
            latest_predict = max(predict_folders, key=lambda x: os.path.getctime(os.path.join(detect_dir, x)))
            source_path = os.path.join(detect_dir, latest_predict, filename)
            dest_path = os.path.join(PREDICT_FOLDER, filename)
            shutil.copy2(source_path, dest_path)
            
            return render_template('index.html',
                                image_path=filename,
                                timestamp=datetime.now().timestamp(),
                                detections=detections,
                                username=session.get('username'))
                    
        except Exception as e:
            print(f"Error processing image: {str(e)}")
            return render_template('index.html', error=f"Error al procesar la imagen: {str(e)}")
    
    return render_template('index.html', username=session.get('username'))

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
        
        # Convertir y guardar el frame
        frame_bytes = base64.b64decode(frame_data.split(',')[1])
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Generar nombre único para el frame
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        frame_filename = f"frame_{session_id}_{timestamp}.jpg"
        frame_path = os.path.join(UPLOAD_FOLDER, 'webcam_frames', frame_filename)
        
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(frame_path), exist_ok=True)
        
        # Guardar frame
        cv2.imwrite(frame_path, frame)
        
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
                webcam_session.end_time = datetime.utcnow()  # Actualizar end_time
                
                for detection in detections:
                    frame_detection = WebcamFrameDetection(
                        session_id=session_id,
                        frame_number=webcam_session.total_frames,
                        disease_name=detection["class"],
                        confidence=detection["confidence"],
                        frame_path=frame_filename,  # Guardar el nombre del archivo
                        user_id=session['user_id']
                    )
                    db.session.add(frame_detection)
                
                db.session.commit()
        
        return jsonify({
            'status': 'success',
            'detections': detections
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
    
    parser = argparse.ArgumentParser(description="Flask app exposing YOLOv8 models")
    parser.add_argument("--port", default=5000, type=int, help="port number")
    args = parser.parse_args()
    
    app.run(host="0.0.0.0", port=args.port, debug=True)