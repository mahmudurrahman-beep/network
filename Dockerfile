FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 django && chown -R django:django /app
USER django

# Collect static files
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# 🚀 ROBUST STARTUP SCRIPT
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "project4.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
