#!/bin/bash
#
# ZeroCD systemd service installation script
#
# Usage:
#   sudo ./service_install.sh install
#   sudo ./service_install.sh uninstall
#   sudo ./service_install.sh status
#

set -e

SERVICE_NAME="zerocd"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SCRIPT_DIR="/opt/zerocd"

install() {
    echo "Installing ZeroCD service..."

    mkdir -p "${SCRIPT_DIR}"
    cp -r main.py ui input usb net system config.py "${SCRIPT_DIR}/"

    mkdir -p /var/log
    touch /var/log/zerocd.log
    chmod 644 /var/log/zerocd.log

    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}"

    echo "ZeroCD service installed. Use 'systemctl start zerocd' to run."
}

uninstall() {
    echo "Uninstalling ZeroCD service..."

    systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
    systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
    rm -f "${SERVICE_FILE}"
    rm -rf "${SCRIPT_DIR}"
    systemctl daemon-reload

    echo "ZeroCD service uninstalled."
}

status() {
    echo "ZeroCD service status:"
    systemctl status "${SERVICE_NAME}" --no-pager || true
    echo ""
    echo "Log tail:"
    tail -20 /var/log/zerocd.log 2>/dev/null || echo "No log file"
}

case "${1:-}" in
    install)
        install
        ;;
    uninstall)
        uninstall
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {install|uninstall|status}"
        exit 1
        ;;
esac
