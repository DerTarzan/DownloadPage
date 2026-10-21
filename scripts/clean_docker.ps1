# Docker Desktop – Komplettbereinigung
# Datei: docker-clean-all.ps1

$ErrorActionPreference = "Continue"

Write-Host "`n=== DOCKER DESKTOP KOMPLETTBEREINIGUNG ===" -ForegroundColor Red
Write-Host "Alle Container, Images, Volumes und Build-Caches werden gelöscht."
Write-Host "Auch Datenbanken und dauerhaft gespeicherte Docker-Daten gehen verloren.`n" -ForegroundColor Yellow

$confirmation = Read-Host "Zum Fortfahren exakt ALLES-LOESCHEN eingeben"

if ($confirmation -cne "ALLES-LOESCHEN") {
    Write-Host "Abgebrochen. Es wurden keine Löschbefehle ausgeführt." -ForegroundColor Green
    exit
}

# Prüfen, ob Docker erreichbar ist
docker info *> $null

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker ist nicht erreichbar. Starte Docker Desktop und versuche es erneut." -ForegroundColor Red
    exit 1
}

Write-Host "`n[1/6] Container stoppen ..." -ForegroundColor Cyan
$containers = docker ps -aq

if ($containers) {
    docker stop $containers
    docker rm -f $containers
}

Write-Host "`n[2/6] Alle Volumes löschen ..." -ForegroundColor Cyan
$volumes = docker volume ls -q

if ($volumes) {
    docker volume rm -f $volumes
}

Write-Host "`n[3/6] Alle Images löschen ..." -ForegroundColor Cyan
$images = docker image ls -aq | Sort-Object -Unique

if ($images) {
    docker image rm -f $images
}

Write-Host "`n[4/6] Nicht standardmäßige Netzwerke löschen ..." -ForegroundColor Cyan
$networks = docker network ls --filter type=custom -q

if ($networks) {
    docker network rm $networks
}

Write-Host "`n[5/6] Build-Cache löschen ..." -ForegroundColor Cyan
docker builder prune -af
docker buildx prune -af

Write-Host "`n[6/6] Verbliebene ungenutzte Docker-Ressourcen bereinigen ..." -ForegroundColor Cyan
docker system prune -af --volumes

Write-Host "`n=== BEREINIGUNG ABGESCHLOSSEN ===" -ForegroundColor Green
docker system df