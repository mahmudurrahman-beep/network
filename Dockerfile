FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 django && chown -R django:django /app
USER django

# Collect static files (required for WhiteNoise)
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# ✅ FIX: Auto-run migrations before starting (Grok's suggestion)
# Use sh -c to handle multiple commands
CMD ["sh", "-c", "
  echo '🚀 Checking database connection...' && \
  python -c \"
import os, django, time
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project4.settings')
django.setup()
from django.db import connection
for i in range(3):
    try:
        connection.ensure_connection()
        print('✅ Database connected!')
        break
    except Exception as e:
        print(f'Attempt {i+1}/3: {e}')
        if i < 2:
            time.sleep(2)
\" && \
  echo '🔧 Running migrations...' && \
  python manage.py migrate --noinput && \
  echo '✅ Migrations complete!' && \
  echo '🚀 Starting Gunicorn...' && \
  gunicorn project4.wsgi:application --bind 0.0.0.0:\$PORT --workers 2 --timeout 120 --log-level info
"]
