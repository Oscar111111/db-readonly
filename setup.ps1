param(
    [switch]$Upgrade,
    [switch]$Drivers
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Show-OdbcDrivers {
    Write-Host ""
    Write-Host "Available ODBC drivers:"
    try {
        $drivers64 = Get-ItemProperty "HKLM:\SOFTWARE\ODBC\ODBCINST.INI\ODBC Drivers"
        $drivers64.PSObject.Properties |
            Where-Object { $_.Name -notlike "PS*" } |
            ForEach-Object { Write-Host ('driver: "' + $_.Name + '"') }
    } catch {
        Write-Host "Unable to read 64-bit ODBC drivers from registry."
    }
    try {
        $drivers32 = Get-ItemProperty "HKLM:\SOFTWARE\WOW6432Node\ODBC\ODBCINST.INI\ODBC Drivers"
        $drivers32.PSObject.Properties |
            Where-Object { $_.Name -notlike "PS*" } |
            ForEach-Object { Write-Host ('driver: "' + $_.Name + '"') }
    } catch {
        Write-Host "Unable to read 32-bit ODBC drivers from registry."
    }
}

if ($Drivers -and -not $Upgrade) {
    Show-OdbcDrivers
    exit 0
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python was not found. Please install Python 3.11 or later."
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

if ($Upgrade) {
    & $Python -m pip install --upgrade pip
    & $Python -m pip install --upgrade -r requirements.txt
} else {
    & $Python -m pip install -r requirements.txt
}

if (-not (Test-Path "config.local.yaml")) {
    Copy-Item "config.example.yaml" "config.local.yaml"
    Write-Host "Created config.local.yaml. Please edit host, port, schema, and username."
}

Write-Host ""
Write-Host "Setup completed."

Show-OdbcDrivers

Write-Host ""
Write-Host "Set the database password environment variable, for example:"
Write-Host '[Environment]::SetEnvironmentVariable("MOM_INS_RO_PASSWORD", "your_password", "User")'
Write-Host "After setting a User environment variable, reopen the terminal or restart the MCP client."
