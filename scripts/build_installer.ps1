# build_installer.ps1 - Genera dist\SolbaBackups y Output\SolbaSetup-3.0.0.exe
# Uso: .\scripts\build_installer.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "=== SolbaBackups - Build instalador ===" -ForegroundColor Cyan

$Python = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

if (-not (Test-Path (Join-Path $Root "nssm.exe"))) {
    throw "Falta nssm.exe en la raiz del proyecto."
}

$Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $Iscc)) {
    $Iscc = "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
}
if (-not (Test-Path $Iscc)) {
    throw "Inno Setup 6 no encontrado."
}

Write-Host "[1/3] PyInstaller..." -ForegroundColor Yellow
& $Python -m pip install -q pyinstaller==6.20.0 | Out-Null
$DistDir = Join-Path $Root "dist\SolbaBackups"
if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }
& $Python -m PyInstaller solba_web.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }
$Exe = Join-Path $DistDir "SolbaBackups.exe"
if (-not (Test-Path $Exe)) { throw "Missing $Exe" }
Write-Host "  OK: $Exe" -ForegroundColor Green

Write-Host "[2/3] Inno Setup..." -ForegroundColor Yellow
$OutDir = Join-Path $Root "Output"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
& $Iscc (Join-Path $Root "SolbaSetup.iss")
if ($LASTEXITCODE -ne 0) { throw "ISCC failed: $LASTEXITCODE" }

$Installer = Get-ChildItem $OutDir -Filter "SolbaSetup-*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $Installer) { throw "Installer not found in Output" }

Write-Host "[3/3] Done" -ForegroundColor Green
Write-Host "  Installer: $($Installer.FullName)"
Write-Host "  Size MB: $([math]::Round($Installer.Length / 1MB, 1))"
