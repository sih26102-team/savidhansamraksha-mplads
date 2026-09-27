# Local automated deployment helper for Windows
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "   SavidhanSamraksha - Local Docker Deployment        " -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

docker-compose down
docker-compose build --no-cache
docker-compose up -d

Write-Host "`nAll services deployed successfully!" -ForegroundColor Green
Write-Host "Frontend: http://localhost:80" -ForegroundColor Yellow
Write-Host "Backend API: http://localhost:5000" -ForegroundColor Yellow
Write-Host "PostgreSQL: localhost:5433" -ForegroundColor Yellow
