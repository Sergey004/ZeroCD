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
if[ "$EUID" -ne 0 ]; then
    log_error "Please run as root: sudo $0"
    exit 1
fi

# Detect Raspberry Pi via device tree
log_info "Detecting hardware..."
IS_RPI=false
if[ -f /sys/firmware/devicetree/base/model ]; then
    if grep -q "Raspberry" /sys/firmware/devicetree/base/model; then
        IS_RPI=true
        RPI_MODEL=$(cat /sys/firmware/devicetree/base/model)
        log_info "Detected: $RPI_MODEL"
    fi
fi

if [ "$IS_RPI" = false ]; then
    log_warn "Not a Raspberry Pi - USB gadget features will not work natively"
fi

# Update package lists
log_info "Updating package lists..."
apt-get update -qq

# Install system dependencies (Добавлены пакеты для сборки C++ и MTP)
log_info "Installing system dependencies..."
apt-get install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    python3-rpi.gpio python3-spidev python3-pil \
    git wget curl fontconfig hostapd dnsmasq iptables \
    build-essential make gcc libusb-1.0-0-dev \
    || { log_error "Failed to install system packages"; exit 1; }

# Install Python packages
log_info "Installing Python packages..."
pip3 install --break-system-packages -q \
    gpiod pillow keyboard numpy flask requests tqdm \
    || { log_error "Failed to install Python packages"; exit 1; }

# Create ZeroCD user directory
ZEROCD_DIR="/opt/zerocd"
if[ ! -d "$ZEROCD_DIR" ]; then
    log_info "Creating ZeroCD directory..."
    mkdir -p "$ZEROCD_DIR"
fi

# Copy ZeroCD files
log_info "Installing ZeroCD files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -r "$SCRIPT_DIR"/* "$ZEROCD_DIR/" 2>/dev/null || true
mkdir -p /mnt/iso_storage

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

# Install DejaVu Sans font
DEJAVU_DIR="/usr/share/fonts/truetype/dejavu"
if[ ! -d "$DEJAVU_DIR" ]; then
    log_info "Installing DejaVu Sans font..."
    apt-get install -y -qq fonts-dejavu-core || true
fi

# Refresh font cache
log_info "Refreshing font cache..."
fc-cache -f > /dev/null 2>&1 || true

# Install uMTP-Responder
log_info "Installing uMTP-Responder..."
mkdir -p /etc/umtprd
if [ -f "$ZEROCD_DIR/conf/umtprd.conf" ]; then
    cp "$ZEROCD_DIR/conf/umtprd.conf" /etc/umtprd/umtprd.conf
fi

cd "$ZEROCD_DIR/uMTP-Responder"
if command -v make &> /dev/null; then
    make -j$(nproc)
    if[ -f umtprd ]; then
        cp umtprd /usr/local/bin/
        log_info "uMTP-Responder installed"
    else
        log_error "uMTP-Responder compilation failed!"
    fi
else
    log_warn "make not found, skipping uMTP-Responder build"
fi

cd "$ZEROCD_DIR"

# Raspberry Pi Hardware Configuration
if[ "$IS_RPI" = true ]; then
    log_info "Configuring Boot and Kernel Modules..."
    CONFIG_FILE="/boot/firmware/config.txt"
    [ -f /boot/config.txt ] && CONFIG_FILE="/boot/config.txt"

    # 1. Enable SPI for Screen
    if ! grep -q "^dtparam=spi=on" "$CONFIG_FILE"; then
        echo "dtparam=spi=on" >> "$CONFIG_FILE"
        log_info "SPI enabled in $CONFIG_FILE"
    fi

    # 2. Enable DWC2 for USB Gadget (КРИТИЧЕСКИ ВАЖНО)
    if ! grep -q "^dtoverlay=dwc2" "$CONFIG_FILE"; then
        echo "dtoverlay=dwc2" >> "$CONFIG_FILE"
        log_info "USB Gadget Mode (dwc2) enabled in $CONFIG_FILE"
    fi

    # 3. Add modules to autostart
    if ! grep -q "^dwc2" /etc/modules; then echo "dwc2" >> /etc/modules; fi
    if ! grep -q "^libcomposite" /etc/modules; then echo "libcomposite" >> /etc/modules; fi
fi

# Create symlinks and set permissions
log_info "Setting permissions..."
ln -sf "$ZEROCD_DIR" /home/pi/ZeroCD 2>/dev/null || ln -sf "$ZEROCD_DIR" /root/ZeroCD 2>/dev/null || true
chmod +x "$ZEROCD_DIR/main.py" 2>/dev/null || true
chmod +x "$ZEROCD_DIR/scripts/"*.sh 2>/dev/null || true

# Create systemd service
CREATE_SERVICE=false
read -p "Create systemd service for auto-start? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    CREATE_SERVICE=true
fi

if[ "$CREATE_SERVICE" = true ]; then
    log_info "Creating systemd service..."
    cat > /etc/systemd/system/zerocd.service << 'EOF'
[Unit]
Description=ZeroCD USB Emulator
After=local-fs.target network.target

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
fi

echo ""
echo "============================================"
echo -e "${GREEN}  ZeroCD Installation Complete!${NC}"
echo "============================================"
echo ""

if [ "$IS_RPI" = true ]; then
    echo -e "${YELLOW}A reboot is REQUIRED to apply USB and SPI hardware changes.${NC}"
    read -p "Reboot now? [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Rebooting in 5 seconds..."
        sleep 5
        reboot
    fi
fi