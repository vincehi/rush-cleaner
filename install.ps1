# Install derush CLI via uv (no Python required beforehand).
# Usage: irm https://raw.githubusercontent.com/vincentsourice/derush/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

# Install uv if not present
if (!(Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..."
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
}

if (!(Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv was installed but is not in PATH. Restart your terminal or add the uv directory to PATH."
    exit 1
}

# Install derush from GitHub (main)
Write-Host "Installing derush..."
uv tool install "derush @ git+https://github.com/vincentsourice/derush.git"

Write-Host ""
Write-Host "Installation complete. Run:  derush --help"
Write-Host "If 'derush' is not found, restart your terminal or add uv's bin directory to PATH."
Write-Host "Prerequisite: FFmpeg (e.g. winget install FFmpeg / choco install ffmpeg)"
