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

# 🚀 KOYEB PRODUCTION DEPLOYMENT COMMAND
CMD ["sh", "-c", "
  echo '🚀 Starting Network Social Media App...' && \
  echo '📦 Django 6.0.1 | Postgres | Cloudinary' && \
  echo '' && \
  
  # Database connection test
  echo '🔗 Testing database connection...' && \
  python -c \"
import os, django, time, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project4.settings')
django.setup()
from django.db import connection
for i in range(5):
    try:
        connection.ensure_connection()
        print('✅ Database connected successfully!')
        break
    except Exception as e:
        print(f'Attempt {i+1}/5: Database connection failed - {str(e)}')
        if i == 4:
            print('❌ FATAL: Cannot connect to database')
            sys.exit(1)
        time.sleep(3)
  \" && \
  
  # ONLY migrate - NEVER makemigrations in production
  echo '' && \
  echo '🔧 Applying database migrations...' && \
  python manage.py migrate --noinput && \
  
  # Show migration status
  echo '📊 Migration status:' && \
  python manage.py showmigrations --list | grep -E '\[X\]|\[\s\]' && \
  
  # Check if superuser exists, create if not
  echo '' && \
  echo '👑 Checking for superuser...' && \
  python -c \"
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project4.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
if User.objects.filter(is_superuser=True).exists():
    print('✅ Superuser exists')
else:
    print('⚠️  No superuser found. Create one via:')
    print('   koyeb exec -- python manage.py createsuperuser')
  \" && \
  
  # Start Gunicorn
  echo '' && \
  echo '🚀 Starting Gunicorn server...' && \
  echo '📡 App will be available at: https://your-app-name.koyeb.app' && \
  gunicorn project4.wsgi:application \
    --bind 0.0.0.0:\$PORT \
    --workers 3 \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile -
"]
