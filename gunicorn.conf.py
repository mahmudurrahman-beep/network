# gunicorn.conf.py
import multiprocessing
import os

# Worker configuration
workers = int(os.getenv("GUNICORN_WORKERS", 2))
worker_class = "sync"
worker_connections = 1000
timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))
keepalive = 2
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Process naming
proc_name = "network-app"

# Bind address
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# SSL (if using custom domain with SSL)
# keyfile = "/path/to/key.pem"
# certfile = "/path/to/cert.pem"

# Security headers (if behind proxy)
forwarded_allow_ips = "*"
proxy_protocol = True