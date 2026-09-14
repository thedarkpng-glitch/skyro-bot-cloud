# Execute in PowerShell as Administrator.
$ErrorActionPreference = "Stop"

Write-Host "=== BOT HOST PANEL - SETUP ===" -ForegroundColor Cyan

Write-Host "`n[1/5] Verificando Python..." -ForegroundColor Yellow
py --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python nao encontrado. Instale Python 3.14 ou inferior." -ForegroundColor Red
}

Write-Host "`n[2/5] Verificando Node.js..." -ForegroundColor Yellow
node --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "Node.js nao encontrado." -ForegroundColor Red
}

Write-Host "`n[3/5] Instalando dependencias Python..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Write-Host "`n[4/5] Verificando VS Code..." -ForegroundColor Yellow
code --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "VS Code nao encontrado. Tentando instalar via winget..." -ForegroundColor DarkYellow
    winget install --id Microsoft.VisualStudioCode -e --accept-package-agreements --accept-source-agreements
}

Write-Host "`n[5/5] Criando estrutura..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path ".\bots", ".\data" | Out-Null

Write-Host "`nSetup concluido." -ForegroundColor Green
Write-Host "Execute: python app.py"
