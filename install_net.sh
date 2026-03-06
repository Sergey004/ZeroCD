#!/bin/bash
# ZeroCD Quick Install - Clone and install everything from network
# Usage: curl -sL https://raw.githubusercontent.com/Sergey004/ZeroCD/main/install_net.sh | sudo bash

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
if[ -f /sys/firmware/devicetree/base/model ]; then
    if grep -q "Raspberry" /sys/firmware/devicetree/base/model; then
        IS_RPI=true
        RPI_MODEL=$(cat /sys/firmware/devicetree/base/model)
        log_info "Detected: $RPI_MODEL"
    fi
fi

REPO_URL="https://github.com/Sergey004/ZeroCD.git"
INSTALL_DIR="/opt/zerocd"

log_info "Cloning ZeroCD repository..."
if[ -d "$INSTALL_DIR/.git" ]; then
    log_info "Repository already exists, pulling updates..."
    cd "$INSTALL_DIR"
    git pull
else
    rm -rf "$INSTALL_DIR"
    git clone --recurse-submodules "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

log_info "Updating package lists..."
apt-get update -qq

log_info "Installing system dependencies..."
# ИСПРАВЛЕНИЕ: Удален несуществующий fc-cache, добавлен fontconfig и build-essential
apt-get install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    python3-rpi.gpio python3-spidev python3-pil \
    git wget curl fontconfig hostapd dnsmasq iptables \
    build-essential make gcc libusb-1.0-0-dev \
    || { log_error "Failed to install system packages"; exit 1; }

log_info "Installing Python packages..."
pip3 install --break-system-packages -q \
    gpiod pillow keyboard numpy flask requests tqdm \
    || { log_error "Failed to install Python packages"; exit 1; }

log_info "Installing Fonts..."
FONT_DIR="/usr/share/fonts/truetype/fontawesome"
mkdir -p "$FONT_DIR"
if[ ! -f "$FONT_DIR/fa-solid-900.ttf" ]; then
    wget -q "https://use.fontawesome.com/releases/v6.5.1/webfonts/fa-solid-900.ttf" -O "$FONT_DIR/fa-solid-900.ttf"
fi
apt-get install -y -qq fonts-dejavu-core || true
fc-cache -f > /dev/null 2>&1 || true

# Raspberry Pi Hardware Configuration
if [ "$IS_RPI" = true ]; then
    log_info "Configuring Boot Options..."
    CONFIG_FILE="/boot/firmware/config.txt"[ -f /boot/config.txt ] && CONFIG_FILE="/boot/config.txt"
    
    # Enable SPI
    if ! grep -q "^dtparam=spi=on" "$CONFIG_FILE"; then
        echo "dtparam=spi=on" >> "$CONFIG_FILE"
    fi
    
    # Enable DWC2 (КРИТИЧЕСКИ ВАЖНО ДЛЯ USB GADGET)
    if ! grep -q "^dtoverlay=dwc2" "$CONFIG_FILE"; then
        echo "dtoverlay=dwc2" >> "$CONFIG_FILE"
    fi

    # Автозагрузка модулей ядра
    log_info "Enabling kernel modules..."
    if ! grep -q "^dwc2" /etc/modules; then echo "dwc2" >> /etc/modules; fi
    if ! grep -q "^libcomposite" /etc/modules; then echo "libcomposite" >> /etc/modules; fi
    
    # Загружаем "на горячую", чтобы не перезагружаться прямо сейчас для сборки
    modprobe dwc2 2>/dev/null || true
    modprobe libcomposite 2>/dev/null || true
fi

log_info "Installing uMTP-Responder..."
mkdir -p /etc/umtprd
if [ -f "$INSTALL_DIR/conf/umtprd.conf" ]; then
    cp "$INSTALL_DIR/conf/umtprd.conf" /etc/umtprd/umtprd.conf
fi

cd "$INSTALL_DIR/uMTP-Responder"
make -j$(nproc) 2>/dev/null || make
if [ -f umtprd ]; then
    cp umtprd /usr/local/bin/
    log_info "uMTP-Responder installed successfully"
else
    log_warn "uMTP-Responder build failed"
fi

cd "$INSTALL_DIR"

log_info "Setting permissions & creating directories..."
chmod +x "$INSTALL_DIR/main.py" 2>/dev/null || true
chmod +x "$INSTALL_DIR/scripts/"*.sh 2>/dev/null || true
ln -sf "$INSTALL_DIR" /root/ZeroCD 2>/dev/null || true
mkdir -p /root/zerocd
mkdir -p /mnt/iso_storage

# ИСПРАВЛЕНИЕ: Автоматически создаем сервис для сетевой установки
log_info "Setting up systemd service..."
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

echo ""
echo "============================================"
echo -e "${GREEN} ZeroCD Quick Install Complete!${NC}"
echo "============================================"
echo ""
echo "Service is enabled. You can manage it with:"
echo "  sudo systemctl start zerocd"
echo "  sudo systemctl stop zerocd"
echo ""

if [ "$IS_RPI" = true ]; then
    echo -e "${YELLOW}A reboot is REQUIRED to apply hardware changes (SPI/USB).${NC}"
    read -p "Reboot now? [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Rebooting in 5 seconds..."
        sleep 5
        reboot
    fi
fi