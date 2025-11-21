#!/bin/bash
#
# Installation script for SignalController on Debian/Ubuntu
# This script installs all dependencies and sets up the service
#

set -e

echo "=========================================="
echo "SignalController Installation Script"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# Configuration
INSTALL_DIR="/opt/signal-controller"
DATA_DIR="/var/lib/signal-controller"
LOG_DIR="/var/log/signal-controller"
SERVICE_USER="signal"
SIGNAL_CLI_VERSION="0.13.22"

echo "Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$LOG_DIR"

# Install system dependencies
echo "Installing system dependencies..."
apt-get update
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    openjdk-21-jre-headless \
    wget \
    curl \
    nginx \
    sqlite3

# Create service user
echo "Creating service user..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --no-create-home --shell /bin/false "$SERVICE_USER"
    echo "User $SERVICE_USER created"
else
    echo "User $SERVICE_USER already exists"
fi

# Install signal-cli
echo "Installing signal-cli..."
SIGNAL_CLI_DIR="/opt/signal-cli"

# Remove old installation if exists
if [ -d "$SIGNAL_CLI_DIR" ]; then
    echo "Removing old signal-cli installation..."
    rm -rf "$SIGNAL_CLI_DIR"
fi

wget "https://github.com/AsamK/signal-cli/releases/download/v${SIGNAL_CLI_VERSION}/signal-cli-${SIGNAL_CLI_VERSION}.tar.gz" \
    -O /tmp/signal-cli.tar.gz

tar -xzf /tmp/signal-cli.tar.gz -C /opt/
mv "/opt/signal-cli-${SIGNAL_CLI_VERSION}" "$SIGNAL_CLI_DIR"
rm /tmp/signal-cli.tar.gz

# Create symlink
ln -sf "$SIGNAL_CLI_DIR/bin/signal-cli" /usr/local/bin/signal-cli

echo "signal-cli installed: $(signal-cli --version)"

# Copy application files
echo "Installing SignalController application..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(dirname "$SCRIPT_DIR")"

# Only copy if not running from target directory
if [ "$SOURCE_DIR" != "$INSTALL_DIR" ]; then
    cp -r "$SOURCE_DIR/backend" "$INSTALL_DIR/"
    cp -r "$SOURCE_DIR/database" "$INSTALL_DIR/"
    cp -r "$SOURCE_DIR/scripts" "$INSTALL_DIR/"
else
    echo "Already in target directory, skipping file copy"
fi

# Set up Python virtual environment
echo "Setting up Python virtual environment..."
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
deactivate

# Set permissions
echo "Setting permissions..."
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$LOG_DIR"
chmod +x "$INSTALL_DIR/scripts/"*.sh

# Initialize database
echo "Initializing database..."
sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/python3" "$INSTALL_DIR/database/init_db.py" "$DATA_DIR/messages.db"

# Install systemd services
echo "Installing systemd services..."
cp systemd/signal-cli.service /etc/systemd/system/
cp systemd/signal-controller-public.service /etc/systemd/system/
cp systemd/signal-controller-private.service /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Register a phone number with signal-cli:"
echo "   sudo -u $SERVICE_USER signal-cli -a +YOUR_PHONE_NUMBER register"
echo "   sudo -u $SERVICE_USER signal-cli -a +YOUR_PHONE_NUMBER verify CODE"
echo ""
echo "2. Create /etc/signal-controller/.env file with:"
echo "   SIGNAL_PHONE_NUMBER=+YOUR_PHONE_NUMBER"
echo "   SIGNAL_API_KEY=YOUR_SECURE_RANDOM_KEY"
echo "   (Generate key with: openssl rand -hex 32)"
echo ""
echo "3. Generate SSL certificates or use Let's Encrypt"
echo ""
echo "4. Configure Nginx (see nginx/signal-controller.conf)"
echo ""
echo "5. Start services:"
echo "   systemctl enable --now signal-cli"
echo "   systemctl enable --now signal-controller-public"
echo "   systemctl enable --now signal-controller-private"
echo ""
echo "Installation directory: $INSTALL_DIR"
echo "Data directory: $DATA_DIR"
echo "Log directory: $LOG_DIR"
