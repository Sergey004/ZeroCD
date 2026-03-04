#!/bin/bash
# ZeroCD Quick Install - Clone and install everything from network
# Usage: curl -sL https://raw.githubusercontent.com/Sergey004/ZeroCD/main/install_net.sh | sudo bash
# Or: wget -qO- https://raw.githubusercontent.com/Sergey004/ZeroCD/main/install_net.sh | sudo bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "============================================"
echo " ZeroCD Quick Install (Network)"
echo "============================================"
echo ""

if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root: sudo $0"
    exit 1
fi

IS_RPI=false
if [ -f /sys/firmware/devicetree/base/model ]; then
    if grep -q "Raspberry" /sys/firmware/devicetree/base/model; then
        IS_RPI=true
        RPI_MODEL=$(cat /sys/firmware/devicetree/base/model)
        log_info "Detected: $RPI_MODEL"
    fi
fi

REPO_URL="https://github.com/Sergey004/ZeroCD.git"
INSTALL_DIR="/opt/zerocd"

log_info "Cloning ZeroCD repository..."
if [ -d "$INSTALL_DIR/.git" ]; then
    log_info "Repository already exists, pulling updates..."
    cd "$INSTALL_DIR"
    git pull
else
    rm -rf "$INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

log_info "Updating package lists..."
apt-get update -qq

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
    make \
    gcc \
    libusb-1.0-0-dev \
    || { log_error "Failed to install system packages"; exit 1; }

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

log_info "Installing Font Awesome..."
FONT_DIR="/usr/share/fonts/truetype/fontawesome"
mkdir -p "$FONT_DIR"
if [ ! -f "$FONT_DIR/fa-solid-900.ttf" ]; then
    cd "$FONT_DIR"
    wget -q --show-progress "https://use.fontawesome.com/releases/v6.5.1/webfonts/fa-solid-900.ttf" -O fa-solid-900.ttf
    log_info "Font Awesome installed"
fi

log_info "Installing DejaVu Sans font..."
apt-get install -y -qq fonts-dejavu-core || true

log_info "Refreshing font cache..."
fc-cache -f > /dev/null 2>&1 || true

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
    fi

    log_info "Loading USB gadget modules..."
    modprobe libcomposite
    modprobe configfs
fi

log_info "Installing uMTP-Responder..."
mkdir -p /etc/umtprd
cp "$INSTALL_DIR/conf/umtprd.conf" /etc/umtprd/umtprd.conf

cd "$INSTALL_DIR/uMTP-Responder"
make -j$(nproc) 2>/dev/null || make
if [ -f umtprd ]; then
    cp umtprd /usr/local/bin/
    log_info "uMTP-Responder installed"
else
    log_warn "uMTP-Responder build failed"
fi

cd "$INSTALL_DIR"

log_info "Setting permissions..."
chmod +x "$INSTALL_DIR/main.py" 2>/dev/null || true
chmod +x "$INSTALL_DIR/scripts/"*.sh 2>/dev/null || true

ln -sf "$INSTALL_DIR" /root/ZeroCD 2>/dev/null || true

log_info "Creating data directory..."
mkdir -p /root/zerocd
mkdir -p /mnt/iso_storage

log_info "Enabling services..."
systemctl daemon-reload 2>/dev/null || true

echo ""
echo "============================================"
echo -e "${GREEN} ZeroCD Quick Install Complete!${NC}"
echo "============================================"
echo ""
echo "Location: $INSTALL_DIR"
echo ""
echo "To run manually:"
echo " cd $INSTALL_DIR"
echo " sudo python3 main.py"
echo ""
echo "For PC emulation mode:"
echo " ZEROCD_PLATFORM=pc python3 $INSTALL_DIR/main.py"
echo ""

if [ "$IS_RPI" = true ]; then
    echo -e "${YELLOW}Reboot recommended to apply SPI changes${NC}"
    read -p "Reboot now? [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Rebooting in 5 seconds..."
        sleep 5
        reboot
    fi
fi