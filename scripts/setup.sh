#!/usr/bin/env bash
# Initial development environment setup

set -euo pipefail

echo "==> Setting up Celerius development environment"

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "Docker is required but not installed."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Python 3.12+ is required."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js 20+ is required."; exit 1; }
command -v pnpm >/dev/null 2>&1 || { echo "pnpm is required. Run: corepack enable && corepack prepare pnpm@latest --activate"; exit 1; }

# Copy env files
if [ ! -f .env ]; then
  cp infrastructure/.env.example .env
  echo "==> Created .env from template. Please update with your values."
fi

if [ ! -f frontend/.env.local ]; then
  echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > frontend/.env.local
  echo "NEXT_PUBLIC_APP_NAME=Celerius" >> frontend/.env.local
  echo "==> Created frontend/.env.local"
fi

# Start infrastructure
echo "==> Starting Docker services (postgres, redis, mailhog)"
docker compose -f infrastructure/docker-compose.dev.yml up -d postgres redis mailhog

# Wait for postgres
echo "==> Waiting for PostgreSQL..."
until docker exec celerius_postgres pg_isready -U celerius -d celerius_dev >/dev/null 2>&1; do
  sleep 1
done
echo "==> PostgreSQL is ready"

# Backend setup
echo "==> Installing Python dependencies"
cd backend
python3 -m pip install -r requirements.txt -q

echo "==> Running database migrations"
alembic upgrade head

cd ..

# Frontend setup
echo "==> Installing frontend dependencies"
cd frontend
pnpm install --frozen-lockfile
cd ..

echo ""
echo "==> Setup complete!"
echo ""
echo "Start backend:   cd backend && uvicorn app.main:app --reload --port 8000 --no-proxy-headers"
echo "Start frontend:  cd frontend && pnpm dev"
echo "API docs:        http://localhost:8000/docs"
echo "Frontend:        http://localhost:3000"
echo "Email UI:        http://localhost:8025"
