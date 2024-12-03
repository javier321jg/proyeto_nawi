# gunicorn_config.py
timeout = 300  # aumentar a 5 minutos
workers = 1    # reducir a 1 worker para evitar problemas de memoria
worker_class = 'gthread'
threads = 4
preload_app = True  # pre-cargar la aplicación
max_requests = 1000
max_requests_jitter = 50
