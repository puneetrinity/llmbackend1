#!/bin/bash
# docker/setup.sh - One-time DB setup, health check, and seeding

set -e

echo "🔧 Running one-time app setup"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Wait for Postgres to be ready
log "⏳ Waiting for Postgres..."
until pg_isready -d "$DATABASE_URL" > /dev/null 2>&1; do
  sleep 2
done
log "✅ Postgres is ready"

# Run Alembic migrations
log "📂 Running Alembic migrations..."
alembic upgrade head
log "✅ Migrations complete"

# (Optional) Seed data
# log "🌱 Seeding data..."
# python scripts/seed_data.py

log "✅ Setup completed!"
