import multiprocessing

# Número de workers
workers = multiprocessing.cpu_count() * 2 + 1

# Configuración del binding
bind = "0.0.0.0:5000"

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