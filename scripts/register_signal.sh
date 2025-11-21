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

# Try to register, capture output
REGISTER_OUTPUT=$(sudo -u "$SERVICE_USER" "$SIGNAL_CLI" --config "$CONFIG_DIR" -a "$PHONE_NUMBER" register 2>&1) || REGISTER_FAILED=1

echo "$REGISTER_OUTPUT"

# Check if captcha is required
if echo "$REGISTER_OUTPUT" | grep -q "Captcha required"; then
    echo ""
    echo "=========================================="
    echo "CAPTCHA REQUIRED"
    echo "=========================================="
    echo ""
    echo "Steps to get captcha token:"
    echo "1. Open: https://signalcaptchas.org/registration/generate.html"
    echo "2. Complete the captcha"
    echo "3. Right-click on 'Open Signal' button"
    echo "4. Select 'Copy link address'"
    echo "5. Paste the FULL link below"
    echo ""
    echo "Example link format:"
    echo "signalcaptcha://signal-hcaptcha.5fad97ac-7d06-4e97-b2e7-07f5d23fe1a3.registration.signalcaptchas.org"
    echo ""
    read -p "Paste the captcha link here: " CAPTCHA_LINK
    
    if [ -z "$CAPTCHA_LINK" ]; then
        echo "Error: Captcha link cannot be empty"
        exit 1
    fi
    
    # Extract token from link (remove signalcaptcha:// prefix)
    CAPTCHA_TOKEN="${CAPTCHA_LINK#signalcaptcha://}"
    
    echo ""
    echo "Registering with captcha token..."
    sudo -u "$SERVICE_USER" "$SIGNAL_CLI" --config "$CONFIG_DIR" -a "$PHONE_NUMBER" register --captcha "$CAPTCHA_TOKEN"
    echo ""
    echo "Registration request sent! Check your phone for SMS."
fi

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
