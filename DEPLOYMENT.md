# 🚀 SignalController Deployment Guide

## Your Situation
- ✅ Phone with SIM card available for Signal registration
- ✅ DNS record will point to VM IP address
- ✅ Proxmox VM ready to go

## ❓ Important Questions Answered

### Can I remove the SIM card after registration?
**YES! ✅** Once Signal is registered on signal-cli, you can remove the SIM card from your phone.

**Why this works:**
- Signal uses end-to-end encryption and doesn't rely on SMS after initial registration
- signal-cli stores the registration data locally
- The phone number remains registered to Signal, not to the SIM card
- You only need the SIM card for the initial verification code

**However:**
- ⚠️ Keep the SIM card safe - you may need it if you ever need to re-register
- ⚠️ Don't register the same number on another device (it will deregister signal-cli)
- ⚠️ If Signal's servers lose your registration, you'll need the SIM to verify again

### Best Practice:
After successful registration and testing:
1. Keep the SIM card in a safe place (not in the phone)
2. Document which number is registered
3. Test that signal-cli still works after removing SIM
4. Keep backups of `/var/lib/signal-controller/signal-config/`

---

## 📋 Complete Deployment Steps

### Phase 1: Prepare Your Environment (10 minutes)

#### Step 1.1: Prepare Your Proxmox VM
```bash
# SSH into your Proxmox VM
ssh root@your-vm-ip

# Update system
apt update && apt upgrade -y

# Install git
apt install -y git

# Check you have enough space (need ~10GB)
df -h
```

#### Step 1.2: Clone the Repository
```bash
# Clone to /opt
cd /opt
git clone https://github.com/JanKnapen/signal-controller.git
cd signal-controller

# Make scripts executable
chmod +x scripts/*.sh
```

#### Step 1.3: Set Up DNS
**Before continuing, configure your DNS:**
- Point your domain (e.g., `signal.yourdomain.com`) to your VM's public IP
- Wait for DNS propagation (check with: `dig signal.yourdomain.com`)
- Note: You can continue while DNS propagates

---

### Phase 2: Install Dependencies (15 minutes)

#### Step 2.1: Run Installation Script
```bash
# This will install everything
./scripts/install.sh

# The script will:
# - Install Python, Java, Nginx, SQLite
# - Download signal-cli
# - Create service user
# - Set up directories
# - Install Python packages
# - Initialize database
```

**Expected output:**
```
==========================================
Installation Complete!
==========================================
Installation directory: /opt/signal-controller
Data directory: /var/lib/signal-controller
Log directory: /var/log/signal-controller
```

#### Step 2.2: Verify Installation
```bash
# Check signal-cli is installed
signal-cli --version
# Should show: signal-cli 0.13.22

# Check Python environment
/opt/signal-controller/venv/bin/python3 --version

# Check database was created
ls -la /var/lib/signal-controller/messages.db
```

---

### Phase 3: Register Signal Number (10 minutes)

#### Step 3.1: Have Your Phone Ready
- ✅ SIM card inserted in phone
- ✅ Phone can receive SMS
- ✅ Know your phone number with country code (e.g., +1234567890)

#### Step 3.2: Run Registration Script
```bash
# Start registration process
./scripts/register_signal.sh

# You will be prompted for your phone number
# Enter it WITH country code: +1234567890
```

**The script will:**
1. Ask for your phone number
2. Send registration request to Signal
3. Signal will SMS a verification code to your phone
4. You enter the code
5. Registration complete!

#### Step 3.3: Alternative Manual Registration
If the script has issues:
```bash
# Register manually
sudo -u signal signal-cli -a +YOUR_PHONE_NUMBER register

# Wait for SMS code, then verify
sudo -u signal signal-cli -a +YOUR_PHONE_NUMBER verify CODE_FROM_SMS

# Check registration worked
sudo -u signal signal-cli -a +YOUR_PHONE_NUMBER listIdentities
```

#### Step 3.4: Test Signal Registration
```bash
# Try to list registered numbers
sudo -u signal signal-cli -a +YOUR_PHONE_NUMBER receive

# If this works without errors, registration is successful!
```

---

### Phase 4: Configure the Service (10 minutes)

#### Step 4.1: Generate Secure API Key
```bash
# Generate a strong API key
API_KEY=$(openssl rand -hex 32)
echo "Your API Key (SAVE THIS): $API_KEY"

# Copy it somewhere safe! You'll need it to use the API
```

#### Step 4.2: Create Environment Configuration
```bash
# Create config directory
mkdir -p /etc/signal-controller

# Create the .env file
nano /etc/signal-controller/.env
```

**Paste this content (replace with YOUR values):**
```env
# Your Signal phone number (with country code)
SIGNAL_PHONE_NUMBER=+1234567890

# Your secure API key (paste the one generated above)
SIGNAL_API_KEY=paste_your_generated_key_here

# signal-cli REST API URL
SIGNAL_CLI_URL=http://localhost:8080

# Database path
DATABASE_PATH=/var/lib/signal-controller/messages.db

# Base directory
SIGNAL_CONTROLLER_BASE=/opt/signal-controller

# SSL certificate paths (we'll set these up next)
SSL_CERT_FILE=/etc/letsencrypt/live/your-domain.com/fullchain.pem
SSL_KEY_FILE=/etc/letsencrypt/live/your-domain.com/privkey.pem

# Rate limiting
RATE_LIMIT_PUBLIC=60
RATE_LIMIT_PRIVATE=120
```

**Save and exit** (Ctrl+O, Enter, Ctrl+X)

#### Step 4.3: Secure the Configuration
```bash
# Set proper permissions
chmod 600 /etc/signal-controller/.env
chown signal:signal /etc/signal-controller/.env

# Verify
ls -la /etc/signal-controller/.env
# Should show: -rw------- 1 signal signal
```

---

### Phase 5: Get SSL Certificate (15 minutes)

#### Step 5.1: Install Certbot
```bash
apt install -y certbot
```

#### Step 5.2: Stop Nginx Temporarily
```bash
# Stop nginx if running
systemctl stop nginx
```

#### Step 5.3: Get Certificate from Let's Encrypt
```bash
# Replace signal.yourdomain.com with YOUR domain
certbot certonly --standalone -d signal.yourdomain.com

# Follow the prompts:
# - Enter your email address
# - Agree to terms
# - Choose whether to share email with EFF

# Certificate will be saved to:
# /etc/letsencrypt/live/signal.yourdomain.com/
```

#### Step 5.4: Update .env with Correct Domain
```bash
# Edit the .env file
nano /etc/signal-controller/.env

# Update these lines with YOUR domain:
SSL_CERT_FILE=/etc/letsencrypt/live/signal.yourdomain.com/fullchain.pem
SSL_KEY_FILE=/etc/letsencrypt/live/signal.yourdomain.com/privkey.pem
```

#### Step 5.5: Set Up Auto-Renewal
```bash
# Enable certbot timer for automatic renewal
systemctl enable certbot.timer
systemctl start certbot.timer

# Test renewal process
certbot renew --dry-run
```

---

### Phase 6: Configure Nginx (10 minutes)

#### Step 6.1: Edit Nginx Configuration
```bash
# Copy the config file
cp /opt/signal-controller/nginx/signal-controller.conf /etc/nginx/sites-available/signal-controller

# Edit it with your domain
nano /etc/nginx/sites-available/signal-controller
```

**Change these lines (3 places):**
```nginx
# Line ~15: Change to your domain
server_name signal.yourdomain.com;

# Line ~31: Change to your domain
server_name signal.yourdomain.com;

# Lines ~35-36: Change to your domain
ssl_certificate /etc/letsencrypt/live/signal.yourdomain.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/signal.yourdomain.com/privkey.pem;
```

**Save and exit**

#### Step 6.2: Enable the Site
```bash
# Enable site
ln -s /etc/nginx/sites-available/signal-controller /etc/nginx/sites-enabled/

# Remove default site if present
rm -f /etc/nginx/sites-enabled/default

# Test configuration
nginx -t

# Should show:
# nginx: configuration file /etc/nginx/nginx.conf test is successful
```

#### Step 6.3: Start Nginx
```bash
systemctl enable nginx
systemctl start nginx
systemctl status nginx
```

---

### Phase 7: Start Services (5 minutes)

#### Step 7.1: Start signal-cli First
```bash
# Enable and start signal-cli
systemctl enable signal-cli
systemctl start signal-cli

# Wait 10 seconds for it to start
sleep 10

# Check status
systemctl status signal-cli

# Should show: "active (running)"
```

#### Step 7.2: Test signal-cli REST API
```bash
# Test that signal-cli REST API is responding
curl http://localhost:8080/v1/about

# Should return JSON with version info
```

#### Step 7.3: Start SignalController Services
```bash
# Start public interface (webhook receiver)
systemctl enable signal-controller-public
systemctl start signal-controller-public

# Start private interface (API for sending)
systemctl enable signal-controller-private
systemctl start signal-controller-private

# Check all services
systemctl status signal-controller-public
systemctl status signal-controller-private
```

#### Step 7.4: Verify All Services Running
```bash
# Check all at once
systemctl status signal-cli signal-controller-public signal-controller-private nginx

# All should show "active (running)"
```

---

### Phase 8: Configure Firewall (5 minutes)

#### Step 8.1: Install UFW
```bash
apt install -y ufw
```

#### Step 8.2: Configure Rules
```bash
# Allow SSH (IMPORTANT - don't lock yourself out!)
ufw allow 22/tcp

# Allow HTTP (for Let's Encrypt renewal)
ufw allow 80/tcp

# Allow HTTPS (for webhook)
ufw allow 443/tcp

# DENY port 9000 from outside (private API)
ufw deny 9000/tcp

# DENY port 8080 from outside (signal-cli)
ufw deny 8080/tcp

# Check rules before enabling
ufw show added
```

#### Step 8.3: Enable Firewall
```bash
# Enable (will ask for confirmation)
ufw enable

# Check status
ufw status verbose
```

---

### Phase 9: Test Everything (10 minutes)

#### Test 9.1: Health Checks
```bash
# Test private interface (local)
curl http://localhost:9000/health
# Should return: {"status":"healthy",...}

# Test public interface via Nginx (from VM)
curl https://signal.yourdomain.com/health
# Should return: {"status":"healthy",...}

# Test from outside (from your local machine)
curl https://signal.yourdomain.com/health
```

#### Test 9.2: Send a Test Message
```bash
# Export your API key
export SIGNAL_API_KEY="your_api_key_here"

# Send a message to yourself
curl -X POST http://localhost:9000/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $SIGNAL_API_KEY" \
  -d '{
    "to": "+1234567890",
    "message": "Test from SignalController! 🎉"
  }'

# Check your phone - you should receive the message!
```

#### Test 9.3: Check Database
```bash
# Check if messages are being stored
sudo -u signal sqlite3 /var/lib/signal-controller/messages.db \
  "SELECT COUNT(*) FROM messages;"

# View recent messages
sudo -u signal sqlite3 /var/lib/signal-controller/messages.db \
  "SELECT sender_number, message_body, datetime(received_at) FROM messages ORDER BY received_at DESC LIMIT 5;"
```

#### Test 9.4: Send Yourself a Message from Phone
```bash
# Send a message to your registered number from another phone
# Then check if it was received:

# Watch logs in real-time
journalctl -u signal-controller-public -f

# Query via API
curl -X GET "http://localhost:9000/messages?limit=5" \
  -H "X-API-Key: $SIGNAL_API_KEY" | jq
```

#### Test 9.5: Check Logs
```bash
# Check for any errors
journalctl -u signal-cli -n 50 --no-pager
journalctl -u signal-controller-public -n 50 --no-pager
journalctl -u signal-controller-private -n 50 --no-pager

# Check nginx logs
tail -n 50 /var/log/nginx/signal-controller-access.log
tail -n 50 /var/log/nginx/signal-controller-error.log
```

---

### Phase 10: Remove SIM Card (After Testing)

#### Step 10.1: Verify Everything Works
Before removing SIM:
- ✅ All services running
- ✅ Can send messages via API
- ✅ Can receive messages (test by sending to your number)
- ✅ Messages stored in database
- ✅ No errors in logs

#### Step 10.2: Backup Registration Data
```bash
# Create backup of signal-cli configuration
tar -czf signal-cli-backup-$(date +%Y%m%d).tar.gz \
  /var/lib/signal-controller/signal-config/

# Move backup to safe location
mv signal-cli-backup-*.tar.gz /root/

# Note: This contains your Signal registration!
# Keep it safe - you'll need it if you reinstall
```

#### Step 10.3: Remove SIM Card
1. **Test one more time** - send and receive messages
2. **Remove SIM from phone** - put it in a safe place
3. **Test again** - send and receive messages
4. **If still working** - you're good! ✅

**Note:** signal-cli will continue to work without the SIM. The registration is stored locally.

---

## 🎉 Success Checklist

After completing all steps, verify:

- [ ] signal-cli service running: `systemctl status signal-cli`
- [ ] Public interface running: `systemctl status signal-controller-public`
- [ ] Private interface running: `systemctl status signal-controller-private`
- [ ] Nginx running: `systemctl status nginx`
- [ ] Can send messages via API
- [ ] Can receive messages (webhook working)
- [ ] HTTPS certificate valid (no browser warnings)
- [ ] Health checks return 200 OK
- [ ] Messages stored in database
- [ ] Firewall configured (port 9000 blocked)
- [ ] API key is secure (not the default)
- [ ] DNS pointing to correct IP
- [ ] SIM card backed up safely
- [ ] signal-cli config backed up

---

## 📝 Important Information to Save

**Write these down and keep safe:**

1. **Signal Phone Number**: +_______________
2. **API Key**: ________________________________
3. **Domain**: signal.yourdomain.com
4. **VM IP Address**: __.__.__.___
5. **SIM Card Location**: _____________________
6. **Backup Location**: /root/signal-cli-backup-*.tar.gz

---

## 🔧 Daily Operations

### Send a Message
```bash
./scripts/send_message.sh "+1234567890" "Your message here"
```

### Query Messages
```bash
./scripts/query_messages.sh --limit 10
./scripts/query_messages.sh --stats
./scripts/query_messages.sh --sender "+1234567890"
```

### Check Service Status
```bash
systemctl status signal-cli signal-controller-* nginx
```

### View Logs
```bash
journalctl -u signal-controller-public -f
journalctl -u signal-controller-private -f
```

### Restart Services
```bash
systemctl restart signal-cli
systemctl restart signal-controller-public
systemctl restart signal-controller-private
```

---

## 🚨 Troubleshooting Common Issues

### "signal-cli won't start"
```bash
# Check logs
journalctl -u signal-cli -n 50

# Check if phone number is registered
sudo -u signal signal-cli -a +YOUR_NUMBER listIdentities

# Try starting manually
sudo -u signal /opt/signal-cli/bin/signal-cli -a +YOUR_NUMBER daemon
```

### "Certificate error"
```bash
# Check certificate exists
ls -la /etc/letsencrypt/live/signal.yourdomain.com/

# Test renewal
certbot renew --dry-run

# Check nginx config
nginx -t
```

### "Can't send messages"
```bash
# Check signal-cli is running
systemctl status signal-cli

# Test signal-cli directly
curl http://localhost:8080/v1/about

# Check API key is correct
echo $SIGNAL_API_KEY
```

### "Not receiving messages"
```bash
# Check webhook is accessible from outside
curl https://signal.yourdomain.com/health

# Check signal-cli is receiving
sudo -u signal signal-cli -a +YOUR_NUMBER receive

# Check logs
journalctl -u signal-controller-public -f
```

---

## 🔄 Maintenance Tasks

### Weekly
```bash
# Check disk space
df -h

# Check service status
systemctl status signal-cli signal-controller-* nginx

# Check for errors
journalctl --since "1 week ago" -p err
```

### Monthly
```bash
# Update system
apt update && apt upgrade -y

# Check certificate expiration
certbot certificates

# Backup database
cp /var/lib/signal-controller/messages.db \
   /root/messages-backup-$(date +%Y%m%d).db
```

### Every 90 Days
```bash
# Rotate API key
NEW_KEY=$(openssl rand -hex 32)
echo "New API Key: $NEW_KEY"

# Update .env file
nano /etc/signal-controller/.env
# Change SIGNAL_API_KEY=new_key

# Restart private service
systemctl restart signal-controller-private

# Update all clients/scripts with new key
```

---

## 📞 Quick Reference

**Service Ports:**
- 443 → Nginx (HTTPS webhook)
- 8080 → signal-cli REST API (localhost only)
- 8443 → SignalController Public (internal)
- 9000 → SignalController Private (localhost only)

**Config Files:**
- `/etc/signal-controller/.env` - Main configuration
- `/etc/nginx/sites-available/signal-controller.conf` - Nginx config
- `/var/lib/signal-controller/messages.db` - Database

**Logs:**
- `/var/log/nginx/signal-controller-*.log` - Nginx logs
- `journalctl -u signal-cli` - signal-cli logs
- `journalctl -u signal-controller-*` - Application logs

**Scripts:**
- `/opt/signal-controller/scripts/send_message.sh` - Send message
- `/opt/signal-controller/scripts/query_messages.sh` - Query messages
- `/opt/signal-controller/scripts/register_signal.sh` - Register Signal

---

## 🎯 Estimated Timeline

- **Phase 1** (Prepare): 10 minutes
- **Phase 2** (Install): 15 minutes
- **Phase 3** (Register): 10 minutes
- **Phase 4** (Configure): 10 minutes
- **Phase 5** (SSL): 15 minutes
- **Phase 6** (Nginx): 10 minutes
- **Phase 7** (Start): 5 minutes
- **Phase 8** (Firewall): 5 minutes
- **Phase 9** (Test): 10 minutes
- **Phase 10** (SIM): 5 minutes

**Total: ~1.5 hours** (including testing and troubleshooting)

---

## ✅ You're Done!

Your SignalController is now running and you can:
- ✅ Send Signal messages via API
- ✅ Receive Signal messages via webhook
- ✅ Query stored messages
- ✅ Remove the SIM card safely

**Next:** Integrate SignalController into your automation workflows!

---

**Need help?** Check SECURITY.md and README.md for detailed documentation.
