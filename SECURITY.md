# Security Considerations for SignalController

## 🔒 Security Architecture

### Defense in Depth Strategy

SignalController implements multiple layers of security:

1. **Network Separation**: Public and private interfaces on different ports
2. **Authentication**: API key requirement for sensitive operations
3. **Encryption**: HTTPS/TLS for all public communications
4. **Rate Limiting**: Protection against abuse and DoS attacks
5. **Principle of Least Privilege**: Minimal permissions and capabilities

## 🛡️ Threat Model

### Protected Against

✅ **Unauthorized Message Sending**
- Public interface cannot send messages
- Private interface requires authentication
- Firewall rules prevent external access to private interface

✅ **Data Exfiltration**
- Database only accessible via authenticated API
- No direct database access from public interface
- Logs contain no sensitive data

✅ **Denial of Service (Basic)**
- Rate limiting on webhook endpoint
- Connection limits per IP
- Resource limits via systemd
- Nginx buffering and timeouts

✅ **Message Injection**
- Input validation on all endpoints
- SQL injection protection via parameterized queries
- JSON schema validation

✅ **Privilege Escalation**
- Runs as non-root user
- systemd security features enabled
- Read-only file system mounts where possible

### Limitations

⚠️ **Not Protected Against**
- Sophisticated DDoS attacks (use Cloudflare/similar)
- Compromise of underlying OS
- Physical access to server
- Signal protocol vulnerabilities
- Stolen API keys (rotate regularly)

## 🔐 Authentication & Authorization

### API Key Management

**Generation**:
```bash
# Generate a strong API key
openssl rand -hex 32

# Or use Python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

**Storage**:
- Store in `/etc/signal-controller/.env`
- File permissions: `600` (readable only by signal user)
- Never commit to version control
- Never log in plaintext

**Rotation**:
```bash
# Generate new key
NEW_KEY=$(openssl rand -hex 32)

# Update .env file
sudo nano /etc/signal-controller/.env
# Change SIGNAL_API_KEY=new_value

# Restart services
sudo systemctl restart signal-controller-private

# Update any clients/scripts using the old key
```

**Best Practices**:
- Rotate keys every 90 days
- Use different keys for different environments
- Revoke keys immediately if compromised
- Monitor API usage for anomalies

## 🌐 Network Security

### Firewall Configuration

#### Minimum Required Rules

```bash
# UFW (Ubuntu Firewall)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP (Let's Encrypt)
sudo ufw allow 443/tcp  # HTTPS (webhook)
sudo ufw enable

# Block private interface from internet
sudo ufw deny 9000/tcp
```

#### iptables Configuration

```bash
# Flush existing rules (CAREFUL!)
sudo iptables -F

# Default policies
sudo iptables -P INPUT DROP
sudo iptables -P FORWARD DROP
sudo iptables -P OUTPUT ACCEPT

# Allow loopback
sudo iptables -A INPUT -i lo -j ACCEPT

# Allow established connections
sudo iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow SSH (change port if using non-standard)
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Allow HTTP/HTTPS
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Explicitly block private interface from external
sudo iptables -A INPUT -p tcp --dport 9000 ! -s 127.0.0.1 -j DROP
sudo iptables -A INPUT -p tcp --dport 8080 ! -s 127.0.0.1 -j DROP  # signal-cli

# Rate limiting for HTTPS (anti-DoS)
sudo iptables -A INPUT -p tcp --dport 443 -m state --state NEW -m recent --set
sudo iptables -A INPUT -p tcp --dport 443 -m state --state NEW -m recent --update --seconds 60 --hitcount 20 -j DROP

# Save rules
sudo apt-get install iptables-persistent
sudo netfilter-persistent save
```

### Network Isolation (Advanced)

For maximum security, consider network segmentation:

```bash
# Create separate network interfaces
# Public interface: eth0 (internet-facing)
# Private interface: eth1 (internal network only)

# Bind public service to eth0 only
# Bind private service to eth1 only

# In main.py, modify:
# Public: uvicorn.run(public_app, host="<eth0_ip>", ...)
# Private: uvicorn.run(private_app, host="<eth1_ip>", ...)
```

## 🔒 TLS/SSL Configuration

### Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt-get install certbot

# Obtain certificate
sudo certbot certonly --standalone -d your-domain.com

# Auto-renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Test renewal
sudo certbot renew --dry-run
```

### Modern TLS Configuration

The included Nginx configuration uses:
- TLS 1.2 and 1.3 only (no TLS 1.0/1.1)
- Strong cipher suites (ECDHE with AES-GCM)
- Perfect Forward Secrecy (PFS)
- HSTS header for HTTPS enforcement

### Certificate Pinning (Optional)

For API clients, implement certificate pinning:

```python
import httpx

# Pin specific certificate
session = httpx.Client(verify='/path/to/cert.pem')
```

## 🚫 Rate Limiting & DoS Protection

### Nginx Rate Limiting

Current configuration:
- 10 requests/second per IP
- Burst of 20 requests allowed
- 10 concurrent connections per IP

**Adjust as needed**:
```nginx
# In nginx/signal-controller.conf
limit_req_zone $binary_remote_addr zone=webhook_limit:10m rate=5r/s;  # Stricter
limit_req zone=webhook_limit burst=10 nodelay;  # Lower burst
```

### Additional Protection

**fail2ban Integration**:
```bash
# Install fail2ban
sudo apt-get install fail2ban

# Create filter for SignalController
sudo nano /etc/fail2ban/filter.d/signal-controller.conf
```

```ini
[Definition]
failregex = ^<HOST> .* "POST /webhook/signal HTTP/.*" 400
            ^<HOST> .* "POST /webhook/signal HTTP/.*" 403
ignoreregex =
```

```bash
# Create jail
sudo nano /etc/fail2ban/jail.d/signal-controller.conf
```

```ini
[signal-controller]
enabled = true
port = 443
filter = signal-controller
logpath = /var/log/nginx/signal-controller-access.log
maxretry = 10
findtime = 600
bantime = 3600
```

```bash
# Restart fail2ban
sudo systemctl restart fail2ban
```

### Application-Level Rate Limiting

For more granular control, use FastAPI's rate limiting:

```python
# Add to backend/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
public_app.state.limiter = limiter
public_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@public_app.post("/webhook/signal")
@limiter.limit("10/minute")
async def receive_signal_message(request: Request):
    # ... existing code
```

## 🔍 Monitoring & Alerting

### Log Monitoring

**Important logs to monitor**:
```bash
# Failed authentication attempts
sudo journalctl -u signal-controller-private | grep "Invalid API key"

# Unusual message volumes
sudo journalctl -u signal-controller-public | grep "Stored message"

# Service failures
sudo journalctl -u signal-controller-* -p err

# Nginx errors
sudo tail -f /var/log/nginx/signal-controller-error.log
```

### Automated Monitoring

**Create monitoring script**:
```bash
#!/bin/bash
# /opt/signal-controller/scripts/monitor.sh

# Check if services are running
for service in signal-cli signal-controller-public signal-controller-private; do
    if ! systemctl is-active --quiet $service; then
        echo "ALERT: $service is not running"
        # Send alert (email, SMS, etc.)
    fi
done

# Check for high error rates
ERROR_COUNT=$(sudo journalctl -u signal-controller-public --since "1 hour ago" -p err | wc -l)
if [ $ERROR_COUNT -gt 10 ]; then
    echo "ALERT: High error count: $ERROR_COUNT in last hour"
fi

# Check database size
DB_SIZE=$(du -h /var/lib/signal-controller/messages.db | cut -f1)
echo "Database size: $DB_SIZE"
```

**Schedule with cron**:
```bash
sudo crontab -e
# Add: */5 * * * * /opt/signal-controller/scripts/monitor.sh >> /var/log/signal-controller/monitor.log
```

## 🗄️ Data Security

### Database Encryption

**Option 1: File System Encryption (Recommended)**
```bash
# Use LUKS for encrypted partition
sudo apt-get install cryptsetup

# Create encrypted partition
sudo cryptsetup luksFormat /dev/sdX
sudo cryptsetup open /dev/sdX signal_data

# Create filesystem
sudo mkfs.ext4 /dev/mapper/signal_data

# Mount
sudo mount /dev/mapper/signal_data /var/lib/signal-controller
```

**Option 2: SQLite Encryption Extension (SQLCipher)**
```python
# Requires rebuilding with SQLCipher
# Not included in default setup
```

### Backup Security

```bash
#!/bin/bash
# Secure backup script

BACKUP_DIR="/var/backups/signal-controller"
DATE=$(date +%Y%m%d_%H%M%S)
DB_FILE="/var/lib/signal-controller/messages.db"

# Create encrypted backup
sudo -u signal sqlite3 $DB_FILE ".backup /tmp/backup-$DATE.db"
gpg --encrypt --recipient your-email@example.com /tmp/backup-$DATE.db
mv /tmp/backup-$DATE.db.gpg $BACKUP_DIR/
rm /tmp/backup-$DATE.db

# Delete old backups (keep 30 days)
find $BACKUP_DIR -name "*.gpg" -mtime +30 -delete
```

### Data Retention

```sql
-- Delete messages older than 90 days
DELETE FROM messages WHERE received_at < datetime('now', '-90 days');

-- Vacuum to reclaim space
VACUUM;
```

**Automated cleanup**:
```bash
# Add to crontab
0 3 * * 0 /opt/signal-controller/scripts/cleanup_old_messages.sh
```

## 🛠️ System Hardening

### systemd Security Features

Already implemented in service files:
- `NoNewPrivileges=true` - Prevents privilege escalation
- `PrivateTmp=true` - Isolated /tmp directory
- `ProtectSystem=strict` - Read-only /usr, /boot, /efi
- `ProtectHome=true` - No access to home directories
- `ReadWritePaths` - Minimal write access

### Additional Hardening

**Kernel Parameters**:
```bash
sudo nano /etc/sysctl.d/99-signal-controller.conf
```

```ini
# IP Spoofing protection
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1

# Ignore ICMP redirects
net.ipv4.conf.all.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0

# Ignore send redirects
net.ipv4.conf.all.send_redirects = 0

# Disable source packet routing
net.ipv4.conf.all.accept_source_route = 0
net.ipv6.conf.all.accept_source_route = 0

# Log Martians
net.ipv4.conf.all.log_martians = 1

# TCP SYN cookies
net.ipv4.tcp_syncookies = 1

# Increase TCP backlog
net.ipv4.tcp_max_syn_backlog = 2048
```

```bash
sudo sysctl -p /etc/sysctl.d/99-signal-controller.conf
```

### AppArmor Profile (Optional)

```bash
# Create AppArmor profile
sudo nano /etc/apparmor.d/opt.signal-controller
```

```apparmor
#include <tunables/global>

/opt/signal-controller/venv/bin/python3 {
  #include <abstractions/base>
  #include <abstractions/python>

  /opt/signal-controller/** r,
  /var/lib/signal-controller/** rw,
  /var/log/signal-controller/** rw,
  /etc/signal-controller/.env r,

  # Network
  network inet stream,
  network inet6 stream,
}
```

```bash
# Load profile
sudo apparmor_parser -r /etc/apparmor.d/opt.signal-controller
```

## 🚨 Incident Response

### If API Key is Compromised

1. **Immediately rotate key**:
```bash
NEW_KEY=$(openssl rand -hex 32)
sudo nano /etc/signal-controller/.env  # Update SIGNAL_API_KEY
sudo systemctl restart signal-controller-private
```

2. **Review logs for unauthorized access**:
```bash
sudo journalctl -u signal-controller-private --since "7 days ago" | grep "/send"
```

3. **Check for sent messages**:
```bash
sudo sqlite3 /var/lib/signal-controller/messages.db "SELECT * FROM sent_messages ORDER BY sent_at DESC LIMIT 100;"
```

4. **Update all clients** with new API key

### If Server is Compromised

1. **Isolate server** from network
2. **Disable services**:
```bash
sudo systemctl stop signal-controller-*
sudo systemctl stop signal-cli
```
3. **Preserve evidence** (disk image, logs)
4. **Investigate** compromise vector
5. **Rebuild** from clean backup
6. **Rotate** all credentials

## 📋 Security Checklist

Before going to production:

- [ ] Strong API key generated and stored securely
- [ ] Valid SSL/TLS certificate installed
- [ ] Firewall configured (port 9000 blocked externally)
- [ ] Rate limiting configured in Nginx
- [ ] Services running as non-root user
- [ ] Database backups configured
- [ ] Log monitoring enabled
- [ ] fail2ban installed and configured
- [ ] System updates applied
- [ ] Nginx security headers configured
- [ ] HSTS enabled
- [ ] Environment file permissions set to 600
- [ ] SSH key-only authentication (no passwords)
- [ ] Unnecessary services disabled
- [ ] Security patches auto-update configured
- [ ] Monitoring/alerting configured

## 📚 Additional Resources

- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [Signal Protocol Documentation](https://signal.org/docs/)
- [Nginx Security Best Practices](https://nginx.org/en/docs/http/ngx_http_ssl_module.html)
- [systemd Security Features](https://www.freedesktop.org/software/systemd/man/systemd.exec.html)

---

**Remember**: Security is an ongoing process, not a one-time setup. Regularly review and update your security measures.
