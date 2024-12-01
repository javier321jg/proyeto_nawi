from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Campos adicionales para configuraciones del usuario
    theme = db.Column(db.String(20), default='light')
    font_size = db.Column(db.String(20), default='medium')
    email_notifications = db.Column(db.Boolean, default=False)
    summary_frequency = db.Column(db.String(20), default='daily')
    confidence_threshold = db.Column(db.Integer, default=50)
    auto_save = db.Column(db.Boolean, default=True)
    export_format = db.Column(db.String(20), default='pdf')
    include_images = db.Column(db.Boolean, default=True)

    # Relaciones
    detections = db.relationship('Detection', backref='user', lazy=True)
    disease_detections = db.relationship('DiseaseDetection', backref='user', lazy=True)
    webcam_sessions = db.relationship('WebcamDetection', backref='owner', lazy=True)
    webcam_frames = db.relationship('WebcamFrameDetection', backref='owner', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

class Detection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_path = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    total_detections = db.Column(db.Integer, default=0)
    has_diseases = db.Column(db.Boolean, default=False)
    diseases_detected = db.Column(db.String(500))  # Lista separada por comas de enfermedades detectadas
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relación con las detecciones de enfermedades específicas
    disease_detections = db.relationship('DiseaseDetection', backref='detection', lazy=True)

    def __repr__(self):
        return f'<Detection {self.image_path}>'

class DiseaseDetection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    detection_id = db.Column(db.Integer, db.ForeignKey('detection.id'), nullable=False)
    disease_name = db.Column(db.String(100), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    detection_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<DiseaseDetection {self.disease_name} - {self.confidence}>'

class WebcamDetection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stream_type = db.Column(db.String(20), nullable=False)  # 'webcam' o 'rtsp'
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    total_frames = db.Column(db.Integer, default=0)
    total_detections = db.Column(db.Integer, default=0)
    average_confidence = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relación con las detecciones individuales por cuadro
    frame_detections = db.relationship('WebcamFrameDetection', backref='session', lazy=True)

    def __repr__(self):
        return f'<WebcamDetection {self.stream_type} - User {self.user_id}>'

class WebcamFrameDetection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('webcam_detection.id'), nullable=False)
    frame_number = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    disease_name = db.Column(db.String(100))
    confidence = db.Column(db.Float)
    frame_path = db.Column(db.String(200))  # Para guardar frames relevantes con detecciones
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<WebcamFrameDetection Frame {self.frame_number} - {self.disease_name}>'

class DiseaseDescription(db.Model):
    __tablename__ = 'disease_descriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    short_description = db.Column(db.Text, nullable=False)
    cause = db.Column(db.Text, nullable=False)
    effects = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(255))
    recommendations = db.Column(db.Text)  # Nueva columna

    def __repr__(self):
        return f'<Disease {self.name}>'