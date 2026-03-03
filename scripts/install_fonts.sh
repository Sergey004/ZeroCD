#!/bin/bash
# ZeroCD Font Installer
# Downloads Font Awesome for LCD display icons

set -e

FONT_DIR="/usr/share/fonts/truetype/fontawesome"
FONT_URL="https://use.fontawesome.com/releases/v6.5.1/webfonts/fa-solid-900.ttf"
FONT_FILE="fa-solid-900.ttf"

echo "[*] ZeroCD Font Installer"
echo "=========================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "[!] Please run as root (sudo $0)"
    exit 1
fi

# Create font directory
mkdir -p "$FONT_DIR"

# Download Font Awesome if not exists
if [ ! -f "$FONT_DIR/$FONT_FILE" ]; then
    echo "[*] Downloading Font Awesome..."
    cd "$FONT_DIR"
    wget -q --show-progress "$FONT_URL" -O "$FONT_FILE"
    echo "[OK] Font Awesome installed"
else
    echo "[OK] Font Awesome already installed"
fi

# Refresh font cache
echo "[*] Refreshing font cache..."
fc-cache -f > /dev/null 2>&1 || true
echo "[OK] Done!"

echo ""
echo "Font location: $FONT_DIR/$FONT_FILE"
echo "You can now use Font Awesome icons in ZeroCD LCD display"