# Production image for the MemoVerse Django backend.
# Build context is the `backend/` directory (Render Root Directory = backend).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# libpq5: runtime client library some psycopg[binary] wheels still link against.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ /app/requirements/
RUN pip install --no-cache-dir -r requirements/production.txt

COPY app/ /app/

# Baked in at build time; WhiteNoise serves these directly from the app
# process. Uses only the safe defaults already in settings.py, so no real
# secrets or DATABASE_URL are required for the build to succeed.
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# `migrate` runs once per container start, before Gunicorn takes over.
# Safe for a single web service instance; if this is ever scaled to
# multiple instances, move `migrate` to Render's Pre-Deploy Command instead
# (to avoid concurrent migrate runs racing each other).
CMD python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2
