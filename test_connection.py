from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configuración de la base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/fresas'  # Ajusta "root" y la contraseña si tienes una configurada
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modelos
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

@app.route('/')
def test_db_connection():
    try:
        # Intentar listar todos los usuarios como prueba
        users = User.query.all()
        if users:
            return f"Conexión exitosa. Usuarios encontrados: {[user.username for user in users]}"
        else:
            return "Conexión exitosa. No se encontraron usuarios en la tabla."
    except Exception as e:
        return f"Error al conectar con la base de datos: {e}"

if __name__ == '__main__':
    app.run(debug=True)
