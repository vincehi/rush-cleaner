#!/usr/bin/env sh
# Install derush CLI via uv (no Python required beforehand).
# Usage: curl -LsSf https://raw.githubusercontent.com/vincentsourice/derush/main/install.sh | sh

set -e

# Ensure we have curl or wget
if command -v curl >/dev/null 2>&1; then
  DOWNLOAD="curl -LsSf"
elif command -v wget >/dev/null 2>&1; then
  DOWNLOAD="wget -qO-"
else
  echo "Error: need curl or wget to run this script." >&2
  exit 1
fi

# Install uv if not present
if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  $DOWNLOAD https://astral.sh/uv/install.sh | sh
fi

# Ensure uv is on PATH (install script adds to profile but current shell may not have it)
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:${PATH:-}"
if ! command -v uv >/dev/null 2>&1; then
  echo "Error: uv was installed but is not in PATH. Add: export PATH=\"\$HOME/.local/bin:\$PATH\"" >&2
  exit 1
fi

# Install derush from GitHub (main)
echo "Installing derush..."
uv tool install "derush @ git+https://github.com/vincentsourice/derush.git"

echo ""
echo "Installation complete. Run:  derush --help"
echo "If 'derush' is not found, add to your PATH:  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "Prerequisite: FFmpeg (e.g. brew install ffmpeg / apt install ffmpeg)"
