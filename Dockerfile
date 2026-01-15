FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user
RUN useradd -m -u 1000 django && chown -R django:django /app
USER django

EXPOSE 8000

# 🚀 FIX: Always run migrations before starting
CMD ["sh", "-c", "
  echo '🔧 Checking database connection...' && \
  python -c \"
import os, django, time
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project4.settings')
django.setup()
from django.db import connection
for i in range(5):
    try:
        connection.ensure_connection()
        print('✅ Database connected!')
        break
    except Exception as e:
        print(f'Attempt {i+1}/5: Database connection failed: {e}')
        if i < 4:
            time.sleep(2)
else:
    print('❌ Could not connect to database after 5 attempts')
    exit(1)
\" && \
  echo '🚀 Running migrations...' && \
  python manage.py migrate --noinput && \
  echo '✅ Migrations complete!' && \
  echo '🚀 Starting gunicorn...' && \
  gunicorn project4.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
"]
