$ErrorActionPreference = "Stop"

Write-Host "`n=== Detect-Secrets Baseline aktualisieren ===" -ForegroundColor Cyan

# Ins Projektverzeichnis wechseln
Set-Location (Split-Path $PSScriptRoot -Parent)

# Prüfen, ob die Baseline existiert
if (-not (Test-Path ".secrets.baseline")) {
    Write-Error ".secrets.baseline wurde nicht gefunden."
    exit 1
}

# detect-secrets in der aktiven Python-Umgebung sicherstellen
python -m pip install detect-secrets
if ($LASTEXITCODE -ne 0) {
    Write-Error "Installation von detect-secrets fehlgeschlagen."
    exit 1
}

# Baseline mit den versionierten Dateien aktualisieren
$files = @(git ls-files)
if ($LASTEXITCODE -ne 0 -or $files.Count -eq 0) {
    Write-Error "Git-Dateiliste konnte nicht gelesen werden."
    exit 1
}

python -m detect_secrets.main scan --baseline .secrets.baseline $files
if ($LASTEXITCODE -ne 0) {
    Write-Error "Baseline konnte nicht aktualisiert werden."
    exit 1
}

Write-Host "`n=== Geänderte Dateien ===" -ForegroundColor Cyan
git status --short

Write-Host "Baseline update finished. Review changes before committing." -ForegroundColor Green
