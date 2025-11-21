#!/bin/bash
#
# Signal CLI registration helper script
# Guides you through registering a phone number with signal-cli
#

set -e

SERVICE_USER="signal"
SIGNAL_CLI="/usr/local/bin/signal-cli"
CONFIG_DIR="/var/lib/signal-controller/signal-config"

echo "=========================================="
echo "Signal CLI Registration Helper"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# Check if signal-cli is installed
if [ ! -f "$SIGNAL_CLI" ]; then
    echo "Error: signal-cli not found at $SIGNAL_CLI"
    echo "Please run install.sh first"
    exit 1
fi

# Create and set permissions for config directory
echo "Setting up signal-cli configuration directory..."
mkdir -p "$CONFIG_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

# Get phone number
read -p "Enter your phone number (with country code, e.g., +1234567890): " PHONE_NUMBER

if [ -z "$PHONE_NUMBER" ]; then
    echo "Error: Phone number cannot be empty"
    exit 1
fi

# Validate format
if [[ ! "$PHONE_NUMBER" =~ ^\+[0-9]{10,15}$ ]]; then
    echo "Warning: Phone number format may be invalid"
    echo "Expected format: +[country code][number]"
    read -p "Continue anyway? (y/N): " CONTINUE
    if [ "$CONTINUE" != "y" ] && [ "$CONTINUE" != "Y" ]; then
        exit 1
    fi
fi

# Start registration
echo ""
echo "Requesting verification code for $PHONE_NUMBER..."
echo "You will receive an SMS with a verification code."
echo ""

sudo -u "$SERVICE_USER" "$SIGNAL_CLI" --config "$CONFIG_DIR" -a "$PHONE_NUMBER" register

echo ""
echo "Registration request sent!"
echo ""
read -p "Enter the verification code you received: " VERIFICATION_CODE

if [ -z "$VERIFICATION_CODE" ]; then
    echo "Error: Verification code cannot be empty"
    exit 1
fi

# Verify
echo ""
echo "Verifying code..."
sudo -u "$SERVICE_USER" "$SIGNAL_CLI" --config "$CONFIG_DIR" -a "$PHONE_NUMBER" verify "$VERIFICATION_CODE"

echo ""
echo "=========================================="
echo "Registration Complete!"
echo "=========================================="
echo ""
echo "Your phone number $PHONE_NUMBER is now registered."
echo ""
echo "Next steps:"
echo "1. Update /etc/signal-controller/.env:"
echo "   SIGNAL_PHONE_NUMBER=$PHONE_NUMBER"
echo ""
echo "2. Start the signal-cli service:"
echo "   systemctl enable --now signal-cli"
echo ""
echo "3. Test signal-cli:"
echo "   sudo -u $SERVICE_USER signal-cli --config $CONFIG_DIR -a $PHONE_NUMBER receive"
