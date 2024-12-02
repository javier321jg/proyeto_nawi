# Usa una imagen base de Python
FROM python:3.10-slim

# Establece el directorio de trabajo
WORKDIR /app

# Actualiza los repositorios e instala dependencias del sistema necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copia los archivos del proyecto al contenedor
COPY . .

# Instala las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Expone el puerto para Flask
EXPOSE 8080

# Comando para ejecutar la aplicación
CMD ["python", "webapp.py"]

