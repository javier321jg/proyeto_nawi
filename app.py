from flask import Flask, render_template, request, redirect, flash, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import User

app = Flask(__name__)
app.config.from_pyfile('config.py')
app.secret_key = "your_secret_key"  # Cambia esto por una clave segura
db.init_app(app)

# Ruta de inicio de sesión
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']  # Cambiado a 'username'
        password = request.form['password']

        # Verificar si el usuario existe
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id  # Guarda el ID del usuario en la sesión
            flash('Inicio de sesión exitoso', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Nombre de usuario o contraseña incorrectos', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')


# Ruta de registro
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Validar que los campos no estén vacíos
        if not username or not email or not password:
            flash('Todos los campos son obligatorios', 'error')
            return redirect(url_for('register'))

        # Verificar si el usuario ya existe
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('El correo ya está registrado', 'error')
            return redirect(url_for('register'))

        # Crear un nuevo usuario
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')  # Encripta la contraseña
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Usuario registrado exitosamente', 'success')
        return redirect(url_for('login'))

    return render_template('login.html')

# Ruta del dashboard
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:  # Verifica si el usuario está autenticado
        flash('Por favor, inicia sesión primero', 'error')
        return redirect(url_for('login'))

    return render_template('dashboard.html')  # Muestra el dashboard

# Ruta para cerrar sesión
@app.route('/logout')
def logout():
    session.pop('user_id', None)  # Elimina la sesión del usuario
    flash('Has cerrado sesión correctamente', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
