# 🚀 Quick Deployment Guide for Cloudflare Setup

## Your Configuration
- ✅ Domain: `signal-controller.janne.men`
- ✅ Cloudflare handles SSL/TLS
- ✅ SIM card available for Signal registration
- ✅ Server runs HTTP internally, Cloudflare provides HTTPS externally

---

## Step-by-Step Deployment

### 1️⃣ Install on VM (15 min)

```bash
# SSH to your VM
ssh root@your-vm-ip

# Update and install
cd /opt
git clone https://github.com/JanKnapen/signal-controller.git
cd signal-controller
./scripts/install.sh
```

---

### 2️⃣ Register Signal (10 min)

**Have phone with SIM ready!**

```bash
./scripts/register_signal.sh
# Enter: +31612345678 (your number)
# Enter verification code from SMS
```

---

### 3️⃣ Configure Service (5 min)

```bash
# Generate API key
API_KEY=$(openssl rand -hex 32)
echo "Save this: $API_KEY"

# Create config
mkdir -p /etc/signal-controller
nano /etc/signal-controller/.env
```

**Paste (update YOUR values):**
```env
SIGNAL_PHONE_NUMBER=+31612345678
SIGNAL_API_KEY=your_generated_key_here
SIGNAL_CLI_URL=http://localhost:8080
DATABASE_PATH=/var/lib/signal-controller/messages.db
```

**Save and secure:**
```bash
chmod 600 /etc/signal-controller/.env
chown signal:signal /etc/signal-controller/.env
```

---

### 4️⃣ Configure Nginx (5 min)

```bash
# Copy Cloudflare-optimized config
cp nginx/signal-controller-cloudflare.conf /etc/nginx/sites-available/signal-controller

# Enable site
ln -s /etc/nginx/sites-available/signal-controller /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test and start
nginx -t
systemctl enable nginx
systemctl start nginx
```

---

### 5️⃣ Configure Firewall (5 min)

```bash
apt install -y ufw

# Allow only necessary ports
ufw allow 22/tcp      # SSH
ufw allow 80/tcp      # HTTP (Cloudflare connects here)
ufw deny 9000/tcp     # Block private API

# Enable
ufw enable
ufw status
```

---

### 6️⃣ Configure Cloudflare

In Cloudflare dashboard for `signal-controller.janne.men`:

**DNS Settings:**
```
Type: A
Name: signal-controller
Content: YOUR_VM_IP
Proxy: ✅ Proxied (orange cloud)
```

**SSL/TLS Settings:**
- SSL/TLS encryption mode: **Full** (not Full Strict)
- This allows Cloudflare HTTPS → Your server HTTP

**Optional - Restrict to Cloudflare IPs:**
In VM firewall, only allow Cloudflare IP ranges on port 80.

---

### 7️⃣ Start Services (5 min)

```bash
# Start in order
systemctl enable signal-cli
systemctl start signal-cli
sleep 10

# Check signal-cli
systemctl status signal-cli
curl http://localhost:8080/v1/about

# Start SignalController
systemctl enable signal-controller-public
systemctl start signal-controller-public

systemctl enable signal-controller-private
systemctl start signal-controller-private

# Verify all running
systemctl status signal-cli signal-controller-*
```

---

### 8️⃣ Test Everything (10 min)

**Test 1: Health checks**
```bash
# Local
curl http://localhost:8080/health

# External via Cloudflare
curl https://signal-controller.janne.men/health
```

**Test 2: Send message**
```bash
export SIGNAL_API_KEY="your_key"

curl -X POST http://localhost:9000/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $SIGNAL_API_KEY" \
  -d '{"to": "+31612345678", "message": "Test! 🎉"}'
```

Check your phone - you should receive it!

**Test 3: Receive messages**
```bash
# Send a message TO your number from another phone
# Check logs:
journalctl -u signal-controller-public -f

# Query received:
curl "http://localhost:9000/messages?limit=5" \
  -H "X-API-Key: $SIGNAL_API_KEY" | jq
```

---

### 9️⃣ Remove SIM Card (After testing)

Once everything works:

```bash
# Backup registration
tar -czf /root/signal-backup-$(date +%Y%m%d).tar.gz \
  /var/lib/signal-controller/signal-config/

# Test one more time
# Then remove SIM from phone - keep it safe!
```

---

## ✅ Architecture with Cloudflare

```
Internet
   │
   ├─[HTTPS]─► Cloudflare (SSL termination)
              │
              ├─[HTTP]─► Nginx (port 80) on your VM
                         │
                         ├─► Public Interface (port 8080)
                         │   └─► SQLite Database
                         │
              
Internal Network (VM only)
   │
   └─[HTTP]─► Private Interface (port 9000)
              └─► Send messages via signal-cli
```

---

## 🎯 Quick Commands

**Send message:**
```bash
./scripts/send_message.sh "+31612345678" "Hello"
```

**Query messages:**
```bash
./scripts/query_messages.sh --limit 10
```

**Check status:**
```bash
systemctl status signal-controller-*
```

**View logs:**
```bash
journalctl -u signal-controller-public -f
```

---

## 🔒 Security Notes

✅ **Cloudflare handles:**
- SSL/TLS encryption
- DDoS protection
- CDN caching (disable for /webhook/signal)
- Bot protection

✅ **Your server:**
- Runs HTTP internally (Cloudflare connects via HTTP)
- Port 9000 blocked from internet
- API key authentication for private API
- Rate limiting in Nginx

---

## ⏱️ Total Time: ~1 hour

**No SSL certificates needed! Cloudflare handles everything.**

---

## 💡 Cloudflare Tips

**Disable caching for webhook:**
In Cloudflare Page Rules:
```
URL: signal-controller.janne.men/webhook/*
Setting: Cache Level = Bypass
```

**Check Cloudflare is working:**
```bash
curl -I https://signal-controller.janne.men/health
# Should show: cf-ray header
```

---

## 📝 What to Save

- Phone Number: +31612345678
- API Key: [your generated key]
- Domain: signal-controller.janne.men
- Backup: /root/signal-backup-*.tar.gz

---

**You're done! No SSL certificate hassle needed.** 🎉
