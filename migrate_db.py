# migrate_db.py

from webapp import app, db
from models import *
from werkzeug.security import generate_password_hash
import pymysql

def test_connection():
    """Prueba la conexión a la base de datos"""
    try:
        connection = pymysql.connect(
            host='autorack.proxy.rlwy.net',
            port=27853,
            user='root',
            password='DAcnRAsSqsdiVCpYmgydAIbsnpsTTeBN',
            database='railway'
        )
        connection.close()
        return True
    except Exception as e:
        print(f"Error de conexión: {str(e)}")
        return False

def reset_database():
    print("Verificando conexión a la base de datos...")
    if not test_connection():
        print("No se pudo conectar a la base de datos. Verifica las credenciales y la conexión.")
        return

    with app.app_context():
        try:
            # Eliminar todas las tablas existentes
            print("Eliminando tablas existentes...")
            db.drop_all()
            print("Tablas eliminadas correctamente")
            
            # Crear todas las tablas nuevamente
            print("Creando nuevas tablas...")
            db.create_all()
            print("Tablas creadas correctamente")
            
            # Crear usuario admin por defecto
            print("Creando usuario administrador por defecto...")
            admin_user = User(
                username="admin",
                email="admin@example.com",
                password=generate_password_hash("admin123")
            )
            db.session.add(admin_user)
            db.session.commit()
            
            # Verificar que el usuario se creó correctamente
            verify_user = User.query.filter_by(username="admin").first()
            if verify_user:
                print("\n=== Migración Completada Exitosamente ===")
                print("\nDetalles de acceso:")
                print("------------------------")
                print("URL de la base de datos: autorack.proxy.rlwy.net:27853")
                print("Base de datos: railway")
                print("\nCredenciales de administrador:")
                print("------------------------")
                print("Usuario: admin")
                print("Contraseña: admin123")
                print("Email: admin@example.com")
                print("\n¡IMPORTANTE!")
                print("------------------------")
                print("1. Cambia la contraseña del administrador después de iniciar sesión")
                print("2. La base de datos ha sido reiniciada completamente")
                print("3. Todos los datos anteriores han sido eliminados")
            else:
                print("Error: No se pudo verificar la creación del usuario administrador")
            
        except Exception as e:
            print(f"\n¡ERROR durante la migración!")
            print(f"Detalles del error: {str(e)}")
            print("\nRealizando rollback...")
            db.session.rollback()
            print("Rollback completado")
            return False

        return True

if __name__ == "__main__":
    print("\n=== Iniciando Migración de Base de Datos Railway ===\n")
    success = reset_database()
    if success:
        print("\nPuedes iniciar sesión en la aplicación con las credenciales proporcionadas")
    else:
        print("\nLa migración no se completó correctamente. Revisa los errores anteriores")