import multiprocessing

# Número de workers
workers = multiprocessing.cpu_count() * 2 + 1

# Configuración del binding
bind = "0.0.0.0:10000"

# Timeout
timeout = 120

# Configuración de logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Configuración de workers
worker_class = "sync"
worker_connections = 1000

# Configuración de seguridad
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Configuración de keepalive
keepalive = 2

# Configuración de preload
preload_app = True

# Configuración de max requests
max_requests = 1000
max_requests_jitter = 50 