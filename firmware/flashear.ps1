# Sube build\ a la XIAO ESP32S3 Sense. Uso: .\flashear.ps1 [-Puerto COM5] [-Monitor]
# El puerto sale del parametro o de XIAO_PUERTO en .env.
param(
    [string]$Puerto = "",
    [switch]$Monitor,
    [string]$Psram = $(if ($env:PSRAM) { $env:PSRAM } else { "opi" })
)
$ErrorActionPreference = "Stop"

$Fqbn = "esp32:esp32:XIAO_ESP32S3:PSRAM=$Psram"
$Raiz = Split-Path -Parent $PSScriptRoot
$Cli = $env:ARDUINO_CLI
if (-not $Cli) {
    $cmd = Get-Command arduino-cli -ErrorAction SilentlyContinue
    if ($cmd) { $Cli = $cmd.Source } else { $Cli = "$env:USERPROFILE\bin\arduino-cli.exe" }
}

if (-not $Puerto) {
    $envFile = Join-Path $Raiz ".env"
    if (Test-Path $envFile) {
        $linea = Get-Content $envFile | Where-Object { $_ -match '^XIAO_PUERTO=' } | Select-Object -First 1
        if ($linea) { $Puerto = ($linea -replace '^XIAO_PUERTO=', '').Trim('"', ' ', "`r") }
    }
}
if (-not $Puerto) {
    Write-Host "No hay puerto. Pasalo con -Puerto o define XIAO_PUERTO en .env. Puertos detectados:"
    & $Cli board list
    Write-Host ""
    Write-Host "Si la placa no aparece: manten pulsado BOOT, pulsa y suelta RESET, suelta BOOT (modo bootloader)"
    Write-Host "y vuelve a listar. Cierra el Monitor Serie antes de subir."
    exit 1
}

& $Cli upload -p $Puerto --fqbn $Fqbn --input-dir (Join-Path $Raiz "build")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($Monitor) { & $Cli monitor -p $Puerto -c baudrate=115200 }
