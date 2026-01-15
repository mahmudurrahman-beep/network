#!/bin/bash
set -e

echo "🔧 Checking database connection..."
python << END
import os
import sys
import time
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project4.settings')
django.setup()

from django.db import connection

max_retries = 5
for i in range(max_retries):
    try:
        connection.ensure_connection()
        print(f"✅ Database connected! (Attempt {i+1}/{max_retries})")
        break
    except Exception as e:
        print(f"⚠️  Database connection failed: {e}")
        if i == max_retries - 1:
            print("❌ Could not connect to database. Exiting.")
            sys.exit(1)
        print(f"Retrying in 3 seconds...")
        time.sleep(3)
END

echo "🚀 Running database migrations..."
python manage.py migrate --noinput

echo "✅ Starting application..."
exec "$@"
