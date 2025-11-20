# SignalController - Quick Start Guide

## 📋 Overview

SignalController is a secure, production-ready service for sending and receiving Signal messages on your Proxmox VM. This guide will get you up and running in under 30 minutes.

## 🎯 What You'll Have

After following this guide:
- ✅ signal-cli REST API running on port 8080
- ✅ Public webhook interface on port 8443 (HTTPS)
- ✅ Private API on port 9000 (localhost only)
- ✅ SQLite database storing all received messages
- ✅ Nginx reverse proxy with rate limiting
- ✅ systemd services with auto-restart
- ✅ Secure configuration with API key authentication

## ⚡ Quick Installation (5 Steps)

### 1. Clone and Install
```bash
cd /opt
sudo git clone https://github.com/JanKnapen/signal-controller.git
cd signal-controller
sudo chmod +x scripts/*.sh
sudo ./scripts/install.sh
```

### 2. Register Signal Number
```bash
sudo ./scripts/register_signal.sh
# Follow the prompts to register your phone number
```

### 3. Configure
```bash
# Generate a secure API key
API_KEY=$(openssl rand -hex 32)

# Create configuration
sudo mkdir -p /etc/signal-controller
sudo tee /etc/signal-controller/.env > /dev/null <<EOF
SIGNAL_PHONE_NUMBER=+1234567890
SIGNAL_API_KEY=$API_KEY
SIGNAL_CLI_URL=http://localhost:8080
DATABASE_PATH=/var/lib/signal-controller/messages.db
SSL_CERT_FILE=/etc/letsencrypt/live/your-domain.com/fullchain.pem
SSL_KEY_FILE=/etc/letsencrypt/live/your-domain.com/privkey.pem
EOF

sudo chmod 600 /etc/signal-controller/.env
sudo chown signal:signal /etc/signal-controller/.env
```

### 4. Get SSL Certificate
```bash
# Using Let's Encrypt
sudo apt-get install certbot
sudo certbot certonly --standalone -d your-domain.com

# OR for testing, use self-signed
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/signal-controller.key \
  -out /etc/ssl/certs/signal-controller.crt
```

### 5. Start Services
```bash
sudo systemctl enable --now signal-cli
sleep 5  # Wait for signal-cli to start
sudo systemctl enable --now signal-controller-public
sudo systemctl enable --now signal-controller-private

# Check status
sudo systemctl status signal-cli signal-controller-*
```

## 🧪 Test Your Installation

### Test 1: Services Running
```bash
# All should show "active (running)"
systemctl status signal-cli
systemctl status signal-controller-public
systemctl status signal-controller-private
```

### Test 2: API Health Checks
```bash
# signal-cli
curl http://localhost:8080/v1/about

# Private interface
curl http://localhost:9000/health

# Public interface (if SSL is configured)
curl -k https://localhost:8443/health
```

### Test 3: Send a Message
```bash
# Set your API key
export SIGNAL_API_KEY="your_key_here"

# Send test message
curl -X POST http://localhost:9000/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $SIGNAL_API_KEY" \
  -d '{
    "to": "+1234567890",
    "message": "Test from SignalController!"
  }'
```

### Test 4: Check Database
```bash
sudo -u signal sqlite3 /var/lib/signal-controller/messages.db \
  "SELECT COUNT(*) FROM messages;"
```

## 🔧 Configure Nginx (Optional but Recommended)

```bash
# Copy config
sudo cp nginx/signal-controller.conf /etc/nginx/sites-available/signal-controller

# Edit domain and SSL paths
sudo nano /etc/nginx/sites-available/signal-controller

# Enable
sudo ln -s /etc/nginx/sites-available/signal-controller /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 🔥 Configure Firewall

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw deny 9000/tcp   # Block private API
sudo ufw enable
```

## 📱 Using SignalController

### Send a Message
```bash
# Using script
./scripts/send_message.sh "+1234567890" "Hello World"

# Using curl
curl -X POST http://localhost:9000/send \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"to": "+1234567890", "message": "Hello"}'
```

### Query Messages
```bash
# Last 10 messages
./scripts/query_messages.sh --limit 10

# Statistics
./scripts/query_messages.sh --stats

# From specific sender
./scripts/query_messages.sh --sender "+1234567890"
```

### View Logs
```bash
# Real-time logs
sudo journalctl -u signal-controller-public -f

# Last 50 entries
sudo journalctl -u signal-controller-private -n 50

# Errors only
sudo journalctl -u signal-cli -p err
```

## 🐛 Common Issues

### "signal-cli not responding"
```bash
# Restart signal-cli
sudo systemctl restart signal-cli

# Check logs
sudo journalctl -u signal-cli -n 50

# Verify registration
sudo -u signal signal-cli -a +YOUR_NUMBER listIdentities
```

### "Connection refused on port 9000"
```bash
# Check if service is running
sudo systemctl status signal-controller-private

# Try starting manually
sudo -u signal /opt/signal-controller/venv/bin/python3 \
  /opt/signal-controller/backend/main.py private
```

### "SSL certificate error"
```bash
# Check certificate exists
sudo ls -la /etc/letsencrypt/live/your-domain.com/

# For testing, use self-signed (see step 4 above)

# Or disable SSL temporarily by modifying main.py to remove SSL parameters
```

### "Database locked" error
```bash
# Check file permissions
sudo ls -la /var/lib/signal-controller/messages.db

# Fix permissions
sudo chown signal:signal /var/lib/signal-controller/messages.db
```

## 📊 Monitoring

### Create Simple Monitor Script
```bash
sudo tee /opt/signal-controller/scripts/check_health.sh > /dev/null <<'EOF'
#!/bin/bash
echo "=== SignalController Health Check ==="
echo -n "signal-cli: "
systemctl is-active signal-cli
echo -n "Public interface: "
systemctl is-active signal-controller-public
echo -n "Private interface: "
systemctl is-active signal-controller-private
echo ""
echo "Database size: $(du -h /var/lib/signal-controller/messages.db | cut -f1)"
echo "Message count: $(sudo -u signal sqlite3 /var/lib/signal-controller/messages.db 'SELECT COUNT(*) FROM messages;')"
EOF

sudo chmod +x /opt/signal-controller/scripts/check_health.sh

# Run it
sudo /opt/signal-controller/scripts/check_health.sh
```

### Setup Cron for Monitoring
```bash
# Check every 5 minutes and log results
sudo crontab -e
# Add: */5 * * * * /opt/signal-controller/scripts/check_health.sh >> /var/log/signal-controller/health.log 2>&1
```

## 🔒 Security Checklist

Before exposing to the internet:

- [ ] Strong API key generated (not the default)
- [ ] Valid SSL certificate installed (not self-signed)
- [ ] Firewall configured (port 9000 blocked externally)
- [ ] Nginx rate limiting configured
- [ ] SIGNAL_PHONE_NUMBER environment variable set
- [ ] .env file permissions set to 600
- [ ] Services running as 'signal' user (not root)
- [ ] fail2ban installed (optional but recommended)
- [ ] Database backups configured
- [ ] Monitoring/alerting setup

## 🚀 Next Steps

1. **Set up webhook** in your Signal app or integrate with services
2. **Configure backup** scripts for the database
3. **Set up monitoring** with Prometheus/Grafana (advanced)
4. **Review SECURITY.md** for hardening options
5. **Test failover** scenarios

## 📚 Documentation

- **Full Documentation**: `README.md`
- **Security Guide**: `SECURITY.md`
- **API Examples**: See `/scripts` directory
- **Service Configuration**: See `/systemd` directory

## 💡 Pro Tips

1. **Save your API key securely**: Store it in a password manager
2. **Use environment-specific keys**: Different keys for dev/staging/prod
3. **Monitor disk space**: Database can grow large over time
4. **Rotate API keys**: Every 90 days for security
5. **Test backups**: Regularly verify you can restore from backup
6. **Keep updated**: `sudo apt update && sudo apt upgrade` regularly

## 🆘 Getting Help

1. Check logs: `sudo journalctl -u signal-controller-* -n 100`
2. Review README.md troubleshooting section
3. Check signal-cli issues: https://github.com/AsamK/signal-cli/issues
4. Verify configuration in `/etc/signal-controller/.env`

## 🎉 Success!

If all tests pass, you now have a fully functional SignalController service!

You can:
- ✅ Receive Signal messages via webhook
- ✅ Send Signal messages via API
- ✅ Query stored messages
- ✅ Monitor service health

Start integrating SignalController into your automation workflows!

---

**Installation Time**: ~15-30 minutes  
**Difficulty**: Intermediate  
**Support**: See README.md and SECURITY.md
