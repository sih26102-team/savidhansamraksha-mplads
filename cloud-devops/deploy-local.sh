#!/usr/bin/env bash
set -e

echo "======================================================"
echo "   SavidhanSamraksha - Local Docker Deployment        "
echo "======================================================"

docker compose down
docker compose build --no-cache
docker compose up -d

echo ""
echo "All services deployed successfully!"
echo "Frontend: http://localhost:80"
echo "Backend API: http://localhost:5000"
echo "PostgreSQL: localhost:5433"
