#!/bin/sh
set -e

echo "Running migrations..."
python manage.py migrate --noinput

if [ "$DJANGO_DEBUG" != "True" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
fi

exec "$@"
