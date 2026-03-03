#!/bin/bash
# ZeroCD Installation Script for Raspberry Pi OS Lite
# Usage: sudo ./install.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "============================================"
echo "  ZeroCD Installer - Raspberry Pi OS Lite"
echo "============================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root: sudo $0"
    exit 1
fi

# Detect Raspberry Pi via device tree
log_info "Detecting hardware..."
IS_RPI=false
if [ -f /sys/firmware/devicetree/base/model ]; then
    if grep -q "Raspberry" /sys/firmware/devicetree/base/model; then
        IS_RPI=true
        RPI_MODEL=$(cat /sys/firmware/devicetree/base/model)
        log_info "Detected: $RPI_MODEL"
    fi
fi

if [ "$IS_RPI" = false ]; then
    log_warn "Not a Raspberry Pi - some features may not work"
fi

# Update package lists
log_info "Updating package lists..."
apt-get update -qq

# Install system dependencies
log_info "Installing system dependencies..."
apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-rpi.gpio \
    python3-spidev \
    python3-pil \
    git \
    wget \
    curl \
    fc-cache \
    hostapd \
    dnsmasq \
    iptables \
    || { log_error "Failed to install system packages"; exit 1; }

# Install Python packages
log_info "Installing Python packages..."
pip3 install --break-system-packages -q \
    gpiod \
    pillow \
    keyboard \
    numpy \
    flask \
    requests \
    tqdm \
    || { log_error "Failed to install Python packages"; exit 1; }

# Create ZeroCD user directory
ZEROCD_DIR="/opt/zerocd"
if [ ! -d "$ZEROCD_DIR" ]; then
    log_info "Creating ZeroCD directory..."
    mkdir -p "$ZEROCD_DIR"
fi

# Copy ZeroCD files
log_info "Installing ZeroCD files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -r "$SCRIPT_DIR"/* "$ZEROCD_DIR/" 2>/dev/null || true

# Install Font Awesome
log_info "Installing Font Awesome..."
FONT_DIR="/usr/share/fonts/truetype/fontawesome"
mkdir -p "$FONT_DIR"

if [ ! -f "$FONT_DIR/fa-solid-900.ttf" ]; then
    cd "$FONT_DIR"
    wget -q --show-progress "https://use.fontawesome.com/releases/v6.5.1/webfonts/fa-solid-900.ttf" -O fa-solid-900.ttf
    log_info "Font Awesome installed"
else
    log_info "Font Awesome already installed"
fi

# Install DejaVu Sans font (if not exists)
DEJAVU_DIR="/usr/share/fonts/truetype/dejavu"
if [ ! -d "$DEJAVU_DIR" ]; then
    log_info "Installing DejaVu Sans font..."
    apt-get install -y -qq fonts-dejavu-core || true
fi

# Refresh font cache
log_info "Refreshing font cache..."
fc-cache -f > /dev/null 2>&1 || true

# Enable SPI interface (Raspberry Pi only)
if [ "$IS_RPI" = true ]; then
    log_info "Enabling SPI interface..."
    if [ -f /boot/firmware/config.txt ] || [ -f /boot/config.txt ]; then
        CONFIG_FILE="/boot/firmware/config.txt"
        [ -f /boot/config.txt ] && CONFIG_FILE="/boot/config.txt"

        if ! grep -q "^dtparam=spi=on" "$CONFIG_FILE"; then
            echo "dtparam=spi=on" >> "$CONFIG_FILE"
            log_info "SPI enabled in $CONFIG_FILE"
        else
            log_info "SPI already enabled"
        fi
    else
        log_warn "Could not find boot config.txt"
    fi
else
    log_info "Skipping SPI configuration (not a Raspberry Pi)"
fi

# Enable SPI device tree
if [ "$IS_RPI" = true ]; then
    log_info "Checking SPI device tree..."
    if [ -d /proc/device-tree/soc/spi@7e204000 ]; then
        log_info "SPI already enabled in device tree"
    fi
fi

# Create symlink for convenience
log_info "Creating symlink..."
ln -sf "$ZEROCD_DIR" /home/pi/ZeroCD 2>/dev/null || \
ln -sf "$ZEROCD_DIR" /root/ZeroCD 2>/dev/null || true

# Set permissions
log_info "Setting permissions..."
chmod +x "$ZEROCD_DIR/main.py" 2>/dev/null || true
chmod +x "$ZEROCD_DIR/scripts/"*.sh 2>/dev/null || true

# Create systemd service (optional)
CREATE_SERVICE=false
read -p "Create systemd service for auto-start? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    CREATE_SERVICE=true
fi

if [ "$CREATE_SERVICE" = true ]; then
    log_info "Creating systemd service..."
    cat > /etc/systemd/system/zerocd.service << 'EOF'
[Unit]
Description=ZeroCD USB CD-ROM Emulator
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/zerocd
ExecStart=/usr/bin/python3 /opt/zerocd/main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable zerocd.service
    log_info "Systemd service created and enabled"
    log_info "Start with: systemctl start zerocd"
fi

echo ""
echo "============================================"
echo -e "${GREEN}  ZeroCD Installation Complete!${NC}"
echo "============================================"
echo ""
echo "Location: $ZEROCD_DIR"
echo ""
echo "To run manually:"
echo "  cd $ZEROCD_DIR"
echo "  sudo python3 main.py"
echo ""
if [ "$CREATE_SERVICE" = true ]; then
    echo "To start on boot:"
    echo "  sudo systemctl start zerocd"
fi
echo ""
echo "For PC emulation mode (testing):"
echo "  ZEROCD_PLATFORM=pc python3 $ZEROCD_DIR/main.py"
echo ""

# Reboot prompt
read -p "Reboot now to apply SPI changes? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "Rebooting in 5 seconds..."
    sleep 5
    reboot
fi