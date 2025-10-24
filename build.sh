#!/usr/bin/env bash
# Build script for Render deployment

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Run migrations (if needed)
python manage.py migrate --noinput

# Create superuser if it doesn't exist (optional)
# python manage.py createsuperuser --noinput --username admin --email admin@example.com
