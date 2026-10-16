$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path ".env")) {
    throw "Keine .env gefunden. Erzeuge zuerst eine lokale Konfiguration mit: python scripts/generate_env.py --local"
}

$environmentLine = Get-Content ".env" | Where-Object { $_ -match '^\s*ENVIRONMENT\s*=' } | Select-Object -Last 1
$environment = if ($environmentLine) {
    ($environmentLine -replace '^\s*ENVIRONMENT\s*=\s*', '' -replace '\s+#.*$', '').Trim().Trim('"').Trim("'")
} else {
    "production"
}
if ($environment -ne "development") {
    throw "Abbruch: .env muss ENVIRONMENT=development enthalten. Dieses Skript ist nur für lokale Entwicklung."
}

$bindLine = Get-Content ".env" | Where-Object { $_ -match '^\s*APP_BIND\s*=' } | Select-Object -Last 1
$appBind = if ($bindLine) {
    ($bindLine -replace '^\s*APP_BIND\s*=\s*', '' -replace '\s+#.*$', '').Trim().Trim('"').Trim("'")
} else {
    "127.0.0.1"
}
if ($appBind -notin @("127.0.0.1", "localhost", "::1")) {
    throw "Abbruch: APP_BIND muss auf Loopback zeigen (127.0.0.1, localhost oder ::1)."
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker wurde nicht gefunden. Starte Docker Desktop und versuche es erneut."
}

$context = (& docker context show).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Docker-Kontext konnte nicht ermittelt werden."
}
$dockerHost = (& docker context inspect $context --format '{{.Endpoints.docker.Host}}').Trim()
if ($LASTEXITCODE -ne 0 -or $dockerHost -notmatch '^(npipe://|unix://|tcp://(localhost|127(?:\.\d{1,3}){3})(:\d+)?$)') {
    throw "Abbruch: Der aktive Docker-Kontext ist nicht eindeutig lokal."
}

Write-Host "Starte die lokale DownloadPage mit Docker Compose (kein Git-Pull oder Deployment)."
& docker compose up -d --build app
if ($LASTEXITCODE -ne 0) {
    throw "Die lokale App oder Datenbank konnte nicht gestartet werden."
}

Write-Host "Füge den lokalen Beispielkatalog ein."
& docker compose exec -T app python scripts/seed_demo_data.py --docker-local
if ($LASTEXITCODE -ne 0) {
    throw "Der Beispielkatalog wurde nicht vollständig angelegt."
}
