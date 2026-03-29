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

# === УСТАНОВКА КАСТОМНОГО ЯДРА ZEROCD ИЗ DEB РЕПО ===
log_info "Adding ZeroCD kernel repository..."

# Добавляем GPG ключ
wget -q -O - https://sergey004.github.io/ZeroCD-kernel-deb/zerocd-kernel.gpg.key | apt-key add - 2>/dev/null || gpg --dearmor -o /etc/apt/trusted.gpg.d/zerocd-kernel-archive-keyring.gpg < <(wget -q -O - https://sergey004.github.io/ZeroCD-kernel-deb/zerocd-kernel.gpg.key)

# Добавляем репозиторий
echo "deb https://sergey004.github.io/ZeroCD-kernel-deb main stable" > /etc/apt/sources.list.d/zerocd-kernel.list

log_info "Updating package lists with new kernel repository..."
apt-get update -qq 2>/dev/null || true

log_info "Installing ZeroCD custom kernel from repository..."
apt-get install -y -qq zerocd-kernel 2>/dev/null || log_warn "Could not install kernel from repository"

# Запасной план: если репо не сработало, ищем локальные пакеты
KERNEL_DIR="$INSTALL_DIR/kernel"
if [ -d "$KERNEL_DIR" ]; then
    DEB_COUNT=$(ls -1 "$KERNEL_DIR"/*.deb 2>/dev/null | wc -l)
    if [ "$DEB_COUNT" -gt 0 ]; then
        log_warn "Found local kernel packages as backup. Using those..."
        dpkg -i "$KERNEL_DIR"/*.deb || true
    fi
fi

log_info "Fixing Raspberry Pi boot hooks (copying custom kernel to firmware)..."
LATEST_VMLINUZ=$(ls -t /boot/vmlinuz-*zerocd* 2>/dev/null | head -n 1)
LATEST_INITRD=$(ls -t /boot/initrd.img-*zerocd* 2>/dev/null | head -n 1)

if [ -z "$LATEST_VMLINUZ" ]; then
    log_warn "No 'zerocd' kernel found, trying latest standard kernel..."
    LATEST_VMLINUZ=$(ls -t /boot/vmlinuz-* 2>/dev/null | head -n 1)
    LATEST_INITRD=$(ls -t /boot/initrd.img-* 2>/dev/null | head -n 1)
fi

if [ -n "$LATEST_VMLINUZ" ] && [ -n "$LATEST_INITRD" ]; then
    log_info "Copying $LATEST_VMLINUZ -> /boot/firmware/kernel8.img"
    cp "$LATEST_VMLINUZ" /boot/firmware/kernel8.img
    
    log_info "Copying $LATEST_INITRD -> /boot/firmware/initramfs8"
    cp "$LATEST_INITRD" /boot/firmware/initramfs8
    
    CONFIG_FILE="/boot/firmware/config.txt"
    [ -f /boot/config.txt ] && CONFIG_FILE="/boot/config.txt"
    if ! grep -q "^initramfs initramfs8" "$CONFIG_FILE"; then
        echo "initramfs initramfs8 followkernel" >> "$CONFIG_FILE"
        log_info "Added initramfs to $CONFIG_FILE"
    fi
    log_info "Custom kernel successfully applied!"
else
    log_warn "Could not find kernel in /boot!"
fi
# ========================================================

log_info "Updating package lists..."
apt-get update -qq

log_info "Installing system dependencies..."
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

if[ "$IS_RPI" = true ]; then
    log_info "Configuring Boot Options..."
    CONFIG_FILE="/boot/firmware/config.txt"
    [ -f /boot/config.txt ] && CONFIG_FILE="/boot/config.txt"
    
    if ! grep -q "^dtparam=spi=on" "$CONFIG_FILE"; then echo "dtparam=spi=on" >> "$CONFIG_FILE"; fi
    if ! grep -q "^dtoverlay=dwc2" "$CONFIG_FILE"; then echo "dtoverlay=dwc2" >> "$CONFIG_FILE"; fi
    if ! grep -q "^dtoverlay=disable-bt" "$CONFIG_FILE"; then echo "dtoverlay=disable-bt" >> "$CONFIG_FILE"; fi

    if ! grep -q "^dwc2" /etc/modules; then echo "dwc2" >> /etc/modules; fi
    if ! grep -q "^libcomposite" /etc/modules; then echo "libcomposite" >> /etc/modules; fi
    
    modprobe dwc2 2>/dev/null || true
    modprobe libcomposite 2>/dev/null || true

    log_info "Optimizing systemd boot time..."
    systemctl disable NetworkManager-wait-online.service 2>/dev/null || true
    systemctl mask NetworkManager-wait-online.service 2>/dev/null || true
    systemctl disable systemd-networkd-wait-online.service 2>/dev/null || true
    systemctl mask systemd-networkd-wait-online.service 2>/dev/null || true
    systemctl disable apt-daily.service 2>/dev/null || true
    systemctl disable apt-daily.timer 2>/dev/null || true
    systemctl disable apt-daily-upgrade.timer 2>/dev/null || true
    systemctl disable apt-daily-upgrade.service 2>/dev/null || true
    systemctl disable ModemManager.service 2>/dev/null || true
    systemctl disable man-db.timer 2>/dev/null || true
    systemctl disable hciuart.service 2>/dev/null || true
    systemctl disable triggerhappy.service 2>/dev/null || true
    
    if systemctl is-active --quiet dphys-swapfile; then
        systemctl stop dphys-swapfile || true
        systemctl disable dphys-swapfile || true
    fi
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

log_info "Setting up systemd services..."

cat > /etc/systemd/system/zerocd.service << 'EOF'
[Unit]
Description=ZeroCD USB Emulator
After=local-fs.target network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/zerocd
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 /opt/zerocd/main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

log_info "Setting up Splash Screen service..."
cat > /etc/systemd/system/zerocd-splash.service << 'EOF'
[Unit]
Description=ZeroCD Splash Screen
After=local-fs.target
Before=zerocd.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/zerocd
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 /opt/zerocd/splash.py
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable zerocd.service
systemctl enable zerocd-splash.service

echo ""
echo "============================================"
echo -e "${GREEN} ZeroCD Quick Install Complete!${NC}"
echo "============================================"

if[ "$IS_RPI" = true ]; then
    echo -e "${YELLOW}A reboot is REQUIRED to apply Kernel and hardware changes.${NC}"
    read -p "Reboot now? [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Rebooting in 5 seconds..."
        sleep 5
        reboot
    fi
fi