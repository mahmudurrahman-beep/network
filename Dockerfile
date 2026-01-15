FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy app
COPY . .

# Create user for security
RUN useradd -m -u 1000 django && chown -R django:django /app
USER django

# Collect static
RUN python manage.py collectstatic --noinput

# Test database connection before starting
CMD ["sh", "-c", "
  echo 'Testing database connection...' && \
  python -c \"
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project4.settings')
django.setup()
from django.db import connection
connection.ensure_connection()
print('✅ Database connection successful!')
\" && \
  echo 'Running migrations...' && \
  python manage.py migrate --noinput && \
  echo 'Starting gunicorn...' && \
  gunicorn project4.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
"]

EXPOSE 8000
