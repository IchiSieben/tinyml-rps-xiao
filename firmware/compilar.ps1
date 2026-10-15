# Compila el firmware para la XIAO ESP32S3 Sense con arduino-cli.
# Uso: .\compilar.ps1 -Zip <libreria_parcheada_xiao.zip>   |   .\compilar.ps1 -PruebaEntorno
param(
    [string]$Zip = "",
    [switch]$PruebaEntorno,
    [string]$Core = $(if ($env:CORE_ESP32) { $env:CORE_ESP32 } else { "3.3.12" }),
    [string]$Psram = $(if ($env:PSRAM) { $env:PSRAM } else { "opi" })
)
$ErrorActionPreference = "Stop"

$Fqbn = "esp32:esp32:XIAO_ESP32S3:PSRAM=$Psram"
$UrlIndice = "https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json"
$Raiz = Split-Path -Parent $PSScriptRoot
$Build = Join-Path $Raiz "build"

$Cli = $env:ARDUINO_CLI
if (-not $Cli) {
    $cmd = Get-Command arduino-cli -ErrorAction SilentlyContinue
    if ($cmd) { $Cli = $cmd.Source }
    elseif (Test-Path "$env:USERPROFILE\bin\arduino-cli.exe") { $Cli = "$env:USERPROFILE\bin\arduino-cli.exe" }
}
if (-not $Cli) {
    Write-Error "No se encontro arduino-cli. Instalalo con: winget install ArduinoSA.CLI (o define ARDUINO_CLI con la ruta)."
}

if ($Core -match "alpha|rc|beta") { Write-Error "Version de core no estable ($Core): usa una 3.3.x estable." }
if (-not $PruebaEntorno -and -not $Zip) { Write-Error "Falta -Zip con la libreria parcheada, o usa -PruebaEntorno." }

function Invoke-ArduinoCli { & $Cli @args; if ($LASTEXITCODE -ne 0) { throw "arduino-cli fallo: $args" } }

try { & $Cli config init --overwrite *> $null } catch {}
try { & $Cli config add board_manager.additional_urls $UrlIndice *> $null } catch {}
Invoke-ArduinoCli core update-index
if (-not ((& $Cli core list) -match "esp32:esp32\s+$([regex]::Escape($Core))")) {
    Invoke-ArduinoCli core install "esp32:esp32@$Core"
}

$Tmp = Join-Path ([IO.Path]::GetTempPath()) ("xiao_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $Tmp | Out-Null
New-Item -ItemType Directory -Force -Path $Build | Out-Null
try {
    if ($PruebaEntorno) {
        $Datos = (& $Cli config get directories.data).Trim()
        $Origen = Join-Path $Datos "packages\esp32\hardware\esp32\$Core\libraries\ESP32\examples\Camera\CameraWebServer"
        if (-not (Test-Path $Origen)) { throw "No existe $Origen" }
        $Dest = Join-Path $Tmp "CameraWebServer"
        Copy-Item $Origen $Dest -Recurse
        $ino = Join-Path $Dest "CameraWebServer.ino"
        $txt = Get-Content $ino -Raw
        $txt = $txt -replace '(?m)^[ \t]*#define[ \t]+CAMERA_MODEL_', '//#define CAMERA_MODEL_'
        $txt = $txt -replace '(?m)^//[ \t]*#define[ \t]+CAMERA_MODEL_XIAO_ESP32S3', '#define CAMERA_MODEL_XIAO_ESP32S3'
        [IO.File]::WriteAllText($ino, $txt, (New-Object Text.UTF8Encoding $false))
        Invoke-ArduinoCli compile --fqbn $Fqbn --output-dir (Join-Path $Build "prueba_entorno") $Dest
        return
    }

    $Lib = Join-Path $Tmp "lib"
    Expand-Archive -Path $Zip -DestinationPath $Lib
    $props = Get-ChildItem $Lib -Recurse -Filter library.properties | Select-Object -First 1
    if (-not $props) { throw "El ZIP no contiene library.properties." }
    $LibDir = $props.DirectoryName
    $Sketch = Join-Path $LibDir "examples\esp32\esp32_camera"
    $ino = Join-Path $Sketch "esp32_camera.ino"
    if (-not (Test-Path $ino)) { throw "Falta esp32_camera.ino en el ZIP." }
    if (-not (Select-String -Path $ino -Pattern "xiao_pins.h" -Quiet)) {
        throw "El ZIP no esta parcheado: corre parchear_libreria.py primero."
    }
    Invoke-ArduinoCli compile --fqbn $Fqbn --library $LibDir --output-dir $Build $Sketch
    Write-Host "Binarios en $Build"
}
finally {
    Remove-Item $Tmp -Recurse -Force -ErrorAction SilentlyContinue
}
