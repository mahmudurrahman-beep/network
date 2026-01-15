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

# Create non-root user
RUN useradd -m -u 1000 django && chown -R django:django /app
USER django

# Collect static files
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Start command
CMD ["sh", "-c", "
  python manage.py migrate --noinput && \
  gunicorn project4.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
"]
