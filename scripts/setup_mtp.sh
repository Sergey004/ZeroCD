#!/bin/bash
# Setup FunctionFS for MTP and start uMTP-Responder
# This script configures USB gadget in FunctionFS mode for MTP

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONF_FILE="/etc/umtprd/umtprd.conf"
MOUNT_POINT="/dev/ffs-mtp"
GADGET_NAME="zerocd"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit 1
fi

# Load composite driver
modprobe libcomposite

# Unmount if already mounted
if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
    umount "$MOUNT_POINT" 2>/dev/null || true
fi

# Unbind UDC if gadget exists (but don't remove system configfs structure)
if [ -f "/sys/kernel/config/usb_gadget/$GADGET_NAME/UDC" ]; then
    echo "" > /sys/kernel/config/usb_gadget/"$GADGET_NAME"/UDC 2>/dev/null || true
    sleep 1
fi

# Create configfs structure
mkdir -p /sys/kernel/config/usb_gadget/$GADGET_NAME
cd /sys/kernel/config/usb_gadget/$GADGET_NAME

# Set USB IDs
echo 0x0100 > idProduct
echo 0x1D6B > idVendor

# Set strings
mkdir -p strings/0x409
echo "ZeroCD" > strings/0x409/manufacturer
echo "ZeroCD MTP Device" > strings/0x409/product
echo "0123456789" > strings/0x409/serialnumber

# Create configuration
mkdir -p configs/c.1
mkdir -p configs/c.1/strings/0x409
echo "Config 1" > configs/c.1/strings/0x409/configuration
echo 120 > configs/c.1/MaxPower

# Create MTP function
mkdir -p functions/ffs.mtp

# Link MTP function to config
ln -s functions/ffs.mtp configs/c.1

# Mount FunctionFS
mkdir -p "$MOUNT_POINT"
mount -t functionfs mtp "$MOUNT_POINT"

# Check if config file exists
if [ ! -f "$CONF_FILE" ]; then
    echo "Error: Config file $CONF_FILE not found"
    echo "Please run: cp $PROJECT_DIR/conf/umtprd.conf $CONF_FILE"
    exit 1
fi

# Start uMTP-Responder
echo "Starting uMTP-Responder..."
cd "$MOUNT_POINT"
if command -v umtprd &> /dev/null; then
    umtprd &
    echo "uMTP-Responder started"
else
    echo "Error: umtprd not found in PATH"
    echo "Please install uMTP-Responder first"
    exit 1
fi

sleep 1

# Get UDC name
UDC_PATH="/sys/class/udc"
if [ -d "$UDC_PATH" ]; then
    UDC=$(ls $UDC_PATH | head -1)
    if [ -n "$UDC" ]; then
        echo "Binding to UDC: $UDC"
        echo "$UDC" > /sys/kernel/config/usb_gadget/$GADGET_NAME/UDC
        echo "MTP gadget ready"
    else
        echo "No UDC found"
        exit 1
    fi
else
    echo "No UDC directory found"
    exit 1
fi