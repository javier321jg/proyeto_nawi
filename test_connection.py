import pymysql

try:
    # Establecer la conexión usando los datos exactos de DBeaver
    connection = pymysql.connect(
        host='autorack.proxy.rlwy.net',
        user='root',
        password='DAcnRAsSqsdiVCpYmgydAIbsnpsTTeBN',
        database='railway',
        port=27853
    )
    
    print("¡Conexión exitosa!")
    
    # Realizar una consulta simple
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        print("Resultado de prueba:", result)
    
    connection.close()
    
except Exception as e:
    print(f"Error de conexión: {str(e)}")