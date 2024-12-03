# gunicorn_config.py
timeout = 300
workers = 1
worker_class = 'gthread'
threads = 4
preload_app = True
max_requests = 1000
max_requests_jitter = 50
bind = "0.0.0.0:$PORT"
