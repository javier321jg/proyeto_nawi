# Especifica la imagen base de Python con la versión deseada
FROM python:3.10.12

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia los archivos de la aplicación al contenedor
COPY . .

# Instala las dependencias listadas en requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expone el puerto en el que la aplicación correrá
EXPOSE 8000

# Define el comando por defecto para ejecutar la aplicación
CMD ["python", "webapp.py"]
