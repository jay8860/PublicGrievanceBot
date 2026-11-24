# --- SELF-HEALING DASHBOARD BUILD ---

if (!(Test-Path "dashboard/dist")) {
Write-Host "Dashboard build missing. Building at runtime..." -ForegroundColor Yellow

```
Push-Location dashboard

npm install
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Pop-Location

Write-Host "Dashboard build completed successfully." -ForegroundColor Green
```

}
else {
Write-Host "Dashboard build already exists." -ForegroundColor Green
}

# --- START TELEGRAM BOT ---

Write-Host "Starting Telegram Bot..." -ForegroundColor Cyan
Start-Process python -ArgumentList "bot.py" -NoNewWindow

# --- START FASTAPI ---

Write-Host "Starting Dashboard API..." -ForegroundColor Cyan

$Port = if ($env:PORT) { $env:PORT } else { "8000" }

python -m uvicorn api:app --host 0.0.0.0 --port $Port
