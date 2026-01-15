FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    git \
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

# 🚀 DOCKER-ONLY MIGRATION WORKFLOW (With Persistence)
CMD ["sh", "-c", "
  echo '🚀 Starting application...' && \
  
  # Step 1: Check if migration files exist
  echo '📂 Checking for existing migration files...' && \
  if [ ! -f /app/network/migrations/0001_initial.py ]; then
    echo '⚠️  No migration files found! Creating initial migrations...' && \
    echo '🔧 Running makemigrations for network app...' && \
    python manage.py makemigrations network --noinput && \
    echo '✅ Created initial migrations!' && \
    echo '📝 Note: These migration files will be lost if container restarts!' && \
    echo '📝 For production: Run makemigrations locally and commit to git.'
  else
    echo '✅ Migration files found. Skipping makemigrations.' && \
    echo 'ℹ️  If models changed, run makemigrations locally and redeploy.'
  fi && \
  
  # Step 2: Always run migrate
  echo '🔧 Applying migrations to database...' && \
  python manage.py migrate --noinput && \
  
  # Step 3: Show migration status
  echo '📊 Migration status:' && \
  python manage.py showmigrations network 2>/dev/null || echo '⚠️  Could not show migrations' && \
  
  # Step 4: Start Gunicorn
  echo '🚀 Starting Gunicorn server...' && \
  gunicorn project4.wsgi:application --bind 0.0.0.0:\$PORT --workers 2 --timeout 120 --log-level info
"]
