#!/bin/bash
# build.sh - Build script for Koyeb

echo "🔨 Building Network App..."

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Run migrations (if needed - Koyeb runs this separately)
# python manage.py migrate --noinput

echo "✅ Build completed!"