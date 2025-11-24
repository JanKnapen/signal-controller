# SignalController# SignalController



A FastAPI-based service for sending and receiving Signal messages via signal-cli REST API.A secure service for receiving and sending Signal messages via signal-cli REST API, designed to run on a Proxmox VM.



## Features## 🏗️ Architecture



- **Send Messages**: REST API endpoint to send Signal messagesSignalController consists of two separate interfaces:

- **Receive Messages**: Automatic processing of incoming messages via SSE stream

- **Message Storage**: SQLite database for message history and conversations### 1. **Public Interface** (Port 8443, exposed to internet)

- **Dual Interface**: - **Purpose**: Receives incoming Signal messages via webhook

  - Public (port 8888): Receives messages from signal-cli- **Security**: Rate-limited, HTTPS only, no sending capabilities

  - Private (port 9000): API for sending messages (localhost only)- **Endpoints**:

- **Security**: API key authentication, Cloudflare SSL termination  - `POST /webhook/signal` - Webhook for incoming messages

  - `GET /health` - Health check

## Architecture

### 2. **Private Interface** (Port 9000, internal only)

```- **Purpose**: Send messages and query stored messages

Internet → Cloudflare → Cloudflare Tunnel → VM:8888 (public) → signal-cli:8080- **Security**: API key authentication, bound to localhost

                                          ↓- **Endpoints**:

Other VMs → localhost:9000 (private API)  - `POST /send` - Send Signal messages

```  - `GET /messages` - Retrieve stored messages

  - `GET /messages/{id}` - Get specific message

## Quick Setup  - `GET /stats` - Get statistics

  - `GET /health` - Health check

### 1. Install

## 📁 Project Structure

```bash

cd /opt```

git clone https://github.com/JanKnapen/signal-controller.gitSignalController/

cd signal-controller├── backend/

sudo ./scripts/install.sh│   ├── main.py              # FastAPI application

```│   ├── config.py            # Configuration management

│   ├── signal_client.py     # signal-cli REST API client

### 2. Register Signal│   └── requirements.txt     # Python dependencies

├── database/

```bash│   ├── db.py               # Database operations

sudo ./scripts/register_signal.sh│   └── init_db.py          # Schema initialization

```├── scripts/

│   ├── install.sh          # Installation script

Follow prompts to register your phone number (requires captcha).│   └── register_signal.sh  # Signal registration helper

├── systemd/

### 3. Configure Environment│   ├── signal-cli.service                  # signal-cli REST service

│   ├── signal-controller-public.service    # Public interface

Create `/etc/signal-controller/.env`:│   └── signal-controller-private.service   # Private interface

├── docker/

```bash│   ├── Dockerfile

SIGNAL_PHONE_NUMBER=+1234567890│   ├── docker-compose.yml

SIGNAL_API_KEY=your_secure_random_key_here│   └── .env.example

```└── README.md

```

Generate key: `openssl rand -hex 32`

## 🚀 Installation

### 4. Setup Cloudflare Tunnel

### Prerequisites

Configure your Cloudflare Tunnel to point to:- Debian/Ubuntu server (tested on Debian 11/12, Ubuntu 20.04/22.04)

```- Root or sudo access

http://YOUR_VM_IP:8888- A registered phone number for Signal

```- Domain name with DNS pointing to your server (for SSL)



### 5. Start Services### Automatic Installation



```bash1. **Clone the repository**:

sudo systemctl enable --now signal-cli```bash

sudo systemctl enable --now signal-controller-publiccd /opt

sudo systemctl enable --now signal-controller-privategit clone https://github.com/JanKnapen/signal-controller.git

```cd signal-controller

```

## API Usage

2. **Run the installation script**:

### Send Message```bash

chmod +x scripts/install.sh

```bashsudo ./scripts/install.sh

curl -X POST http://localhost:9000/send \```

  -H "Content-Type: application/json" \

  -H "X-API-Key: YOUR_API_KEY" \The script will:

  -d '{- Install system dependencies (Python, Java, etc.)

    "to": "+1234567890",- Download and install signal-cli

    "message": "Hello from SignalController!"- Set up Python virtual environment

  }'- Create service user and directories

```- Initialize the database

- Install systemd services

### Get Messages

### Manual Installation Steps

```bash

curl -X GET "http://localhost:9000/messages?limit=10" \If you prefer manual installation or the script fails:

  -H "X-API-Key: YOUR_API_KEY"

```#### 1. Install Dependencies

```bash

### Get Conversationssudo apt-get update

sudo apt-get install -y python3 python3-pip python3-venv openjdk-21-jre-headless wget curl sqlite3

```bash```

curl -X GET http://localhost:9000/conversations \

  -H "X-API-Key: YOUR_API_KEY"#### 2. Install signal-cli

``````bash

# Download signal-cli

### Get Statisticswget https://github.com/AsamK/signal-cli/releases/download/v0.13.22/signal-cli-0.13.22.tar.gz

tar -xzf signal-cli-0.13.22.tar.gz

```bashsudo mv signal-cli-0.13.22 /opt/signal-cli

curl -X GET http://localhost:9000/stats \sudo ln -s /opt/signal-cli/bin/signal-cli /usr/local/bin/signal-cli

  -H "X-API-Key: YOUR_API_KEY"```

```

#### 3. Create Service User

## File Structure```bash

sudo useradd --system --no-create-home --shell /bin/false signal

``````

signal-controller/

├── backend/          # FastAPI application#### 4. Set Up Directories

├── database/         # SQLite database module```bash

├── scripts/          # Installation & registration scriptssudo mkdir -p /opt/signal-controller

├── systemd/          # Service definitionssudo mkdir -p /var/lib/signal-controller

└── README.mdsudo mkdir -p /var/log/signal-controller

```sudo chown -R signal:signal /opt/signal-controller /var/lib/signal-controller /var/log/signal-controller

```

## Requirements

#### 5. Install Python Dependencies

- Debian/Ubuntu server```bash

- Python 3.8+cd /opt/signal-controller

- Java 21 (for signal-cli)sudo -u signal python3 -m venv venv

- Phone number for Signal registrationsudo -u signal venv/bin/pip install -r backend/requirements.txt

- Cloudflare Tunnel for external access```



## License#### 6. Initialize Database

```bash

MITsudo -u signal venv/bin/python3 database/init_db.py /var/lib/signal-controller/messages.db

```

## 📱 Signal Registration

Register your phone number with signal-cli:

### Option 1: Using Helper Script
```bash
sudo scripts/register_signal.sh
```

### Option 2: Manual Registration
```bash
# Replace +1234567890 with your phone number
sudo -u signal signal-cli -a +1234567890 register

# You will receive an SMS with a verification code
sudo -u signal signal-cli -a +1234567890 verify CODE_HERE
```

## ⚙️ Configuration

### 1. Create Environment File
```bash
sudo mkdir -p /etc/signal-controller
sudo nano /etc/signal-controller/.env
```

Add the following (replace with your values):
```env
# Your Signal phone number
SIGNAL_PHONE_NUMBER=+1234567890

# Generate a secure API key: openssl rand -hex 32
SIGNAL_API_KEY=your_secure_random_key_here

# signal-cli REST API URL
SIGNAL_CLI_URL=http://localhost:8080

# Database path
DATABASE_PATH=/var/lib/signal-controller/messages.db

# SSL certificates (get from Let's Encrypt)
SSL_CERT_FILE=/etc/letsencrypt/live/your-domain.com/fullchain.pem
SSL_KEY_FILE=/etc/letsencrypt/live/your-domain.com/privkey.pem
```

### 2. Set Permissions
```bash
sudo chmod 600 /etc/signal-controller/.env
sudo chown signal:signal /etc/signal-controller/.env
```

### 3. SSL Certificates

#### Option A: Let's Encrypt (Recommended)
```bash
sudo apt-get install certbot
sudo certbot certonly --standalone -d your-domain.com
```

#### Option B: Self-Signed (Testing Only)
```bash
## 🔧 Configure Cloudflare Tunnel

Instead of nginx, this setup uses Cloudflare Tunnel for secure external access:

1. **Install cloudflared on your reverse proxy/edge server**:
```bash
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
```

2. **Configure tunnel** in `/etc/cloudflared/config.yml`:
```yaml
tunnel: YOUR_TUNNEL_ID
credentials-file: /etc/cloudflared/YOUR_TUNNEL_ID.json

ingress:
  - hostname: signal-controller.your-domain.com
    service: http://YOUR_VM_IP:8888
  - service: http_status:404
```

3. **Start cloudflared**:
```bash
sudo systemctl enable --now cloudflared
```

Cloudflare handles SSL/TLS termination, so the app runs on HTTP port 8888.

## 🎯 Start Services

```bash
# Enable and start signal-cli
sudo systemctl enable --now signal-cli

# Wait a few seconds for signal-cli to start, then:
sudo systemctl enable --now signal-controller-public
sudo systemctl enable --now signal-controller-private

# Check status
sudo systemctl status signal-cli
sudo systemctl status signal-controller-public
sudo systemctl status signal-controller-private
```

## 🔥 Firewall Configuration

### Using UFW
```bash
# Allow SSH (if not already)
sudo ufw allow 22/tcp

# Allow port 8888 for Cloudflare Tunnel (or restrict to tunnel server IP)
sudo ufw allow from YOUR_TUNNEL_SERVER_IP to any port 8888

# Block port 9000 from internet (private interface - localhost only)
sudo ufw deny 9000/tcp
sudo ufw deny 9000/tcp

# Enable firewall
sudo ufw enable
```

### Using iptables
```bash
# Allow established connections
sudo iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow SSH
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Allow HTTP/HTTPS
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Block external access to private interface
sudo iptables -A INPUT -p tcp --dport 9000 ! -s 127.0.0.1 -j DROP

# Save rules
sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

## 📡 Usage

### Sending Messages

#### Using the API
```bash
curl -X POST http://localhost:9000/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "to": "+1234567890",
    "message": "Hello from SignalController!"
  }'
```

### Querying Messages

#### Get Recent Messages
```bash
curl -X GET "http://localhost:9000/messages?limit=10" \
  -H "X-API-Key: YOUR_API_KEY"
```

#### Get Conversations
```bash
curl -X GET "http://localhost:9000/conversations" \
  -H "X-API-Key: YOUR_API_KEY"
```

#### Get Statistics
```bash
curl -X GET "http://localhost:9000/stats" \
  -H "X-API-Key: YOUR_API_KEY"
```

#### Filter Messages by Sender
```bash
curl -X GET "http://localhost:9000/messages?sender=%2B1234567890&limit=5" \
  -H "X-API-Key: YOUR_API_KEY"
```

### Checking Logs

```bash
# Application logs
sudo journalctl -u signal-controller-public -f
sudo journalctl -u signal-controller-private -f
sudo journalctl -u signal-cli -f

# File logs
sudo tail -f /var/log/signal-controller/app.log

# Nginx logs
sudo tail -f /var/log/nginx/signal-controller-access.log
sudo tail -f /var/log/nginx/signal-controller-error.log
```

## 🐳 Docker Deployment (Alternative)

### 1. Prepare Environment
```bash
cd docker
cp .env.example .env
# Edit .env with your values
```

### 2. Start Services
```bash
docker-compose up -d
```

### 3. Register Signal (First Time)
```bash
# Enter the signal-cli container
docker exec -it signal-cli /bin/sh

# Register
signal-cli -a +1234567890 register
signal-cli -a +1234567890 verify CODE_HERE
```

## 🔒 Security Hardening

### 1. **Interface Separation**
- ✅ Public interface (port 8443) only receives messages
- ✅ Private interface (port 9000) only accessible from localhost
- ✅ No sending capability on public interface

### 2. **Authentication**
- ✅ Private interface requires API key via `X-API-Key` header
- ✅ Use strong random API keys: `openssl rand -hex 32`
- ✅ Rotate API keys regularly

### 3. **Rate Limiting**
- ✅ Nginx rate limiting on public webhook (10 req/sec default)
- ✅ Connection limiting per IP
- ✅ Adjustable via configuration

### 4. **Network Security**
- ✅ Firewall rules to block direct access to port 9000
- ✅ HTTPS only for public interface
- ✅ Modern TLS configuration (TLS 1.2+)

### 5. **System Hardening**
- ✅ Run as non-root user (`signal`)
- ✅ systemd security features (NoNewPrivileges, ProtectSystem, etc.)
- ✅ Minimal file system access
- ✅ Automatic restart on failure

### 6. **Additional Recommendations**
```bash
# Use fail2ban to prevent brute force
sudo apt-get install fail2ban

# Regular updates
sudo apt-get update && sudo apt-get upgrade

# Monitor logs for suspicious activity
sudo journalctl -u signal-controller-public | grep -i error

# Backup database regularly
sudo crontab -e -u signal
# Add: 0 2 * * * cp /var/lib/signal-controller/messages.db /var/lib/signal-controller/backup/messages-$(date +\%Y\%m\%d).db
```

### 7. **DDoS Protection**
Consider adding Cloudflare or similar CDN/DDoS protection in front of your webhook endpoint.

## 📊 Database Schema

### Messages Table
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_number TEXT NOT NULL,
    sender_name TEXT,
    timestamp INTEGER NOT NULL,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_body TEXT,
    attachments TEXT,  -- JSON
    raw_data TEXT,     -- JSON
    processed BOOLEAN DEFAULT 0
);
```

### Conversations Table
```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_number TEXT UNIQUE NOT NULL,
    contact_name TEXT,
    last_message_at TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Sent Messages Log
```sql
CREATE TABLE sent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient TEXT NOT NULL,
    message_body TEXT,
    attachment_path TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'sent',
    error_message TEXT
);
```

## 🐛 Troubleshooting

### signal-cli not starting
```bash
# Check logs
sudo journalctl -u signal-cli -n 50

# Verify phone number is registered
sudo -u signal signal-cli -a +1234567890 listIdentities

# Test REST API
curl http://localhost:8080/v1/about
```

### Public interface fails to start
```bash
# Check SSL certificates
sudo ls -la /etc/letsencrypt/live/your-domain.com/

# Check environment variables
sudo -u signal cat /etc/signal-controller/.env

# Test without systemd
sudo -u signal /opt/signal-controller/venv/bin/python3 /opt/signal-controller/backend/main.py public
```

### Database errors
```bash
# Check database file
sudo -u signal sqlite3 /var/lib/signal-controller/messages.db ".tables"

# Reinitialize if corrupted
sudo -u signal /opt/signal-controller/venv/bin/python3 /opt/signal-controller/database/init_db.py /var/lib/signal-controller/messages.db
```

### Webhook not receiving messages
```bash
# Check Nginx configuration
sudo nginx -t

# Check if signal-cli is forwarding to webhook
# In signal-cli config, ensure webhook URL is set

# Test webhook manually
curl -k -X POST https://your-domain.com/webhook/signal \
  -H "Content-Type: application/json" \
  -d '{"envelope":{"sourceNumber":"+1234567890","dataMessage":{"message":"test"}},"account":"+0987654321"}'
```

## 📝 API Documentation

### Public Interface (Port 8443)

#### POST /webhook/signal
Receives incoming Signal messages from signal-cli.

**Request Body**:
```json
{
  "envelope": {
    "sourceNumber": "+1234567890",
    "sourceName": "John Doe",
    "timestamp": 1234567890000,
    "dataMessage": {
      "message": "Hello!",
      "attachments": []
    }
  },
  "account": "+0987654321"
}
```

**Response**:
```json
{
  "status": "success",
  "message_id": 123,
  "timestamp": "2024-01-01T12:00:00"
}
```

### Private Interface (Port 9000)

#### POST /send
Send a Signal message.

**Headers**: `X-API-Key: YOUR_API_KEY`

**Request**:
```json
{
  "to": "+1234567890",
  "message": "Hello World",
  "attachment": "/path/to/file.jpg"
}
```

**Response**:
```json
{
  "status": "sent",
  "timestamp": "2024-01-01T12:00:00",
  "recipient": "+1234567890",
  "message_preview": "Hello World"
}
```

#### GET /messages
Retrieve stored messages.

**Headers**: `X-API-Key: YOUR_API_KEY`

**Query Parameters**:
- `limit` (default: 100): Number of messages to return
- `offset` (default: 0): Pagination offset
- `sender` (optional): Filter by sender number

**Response**:
```json
{
  "count": 10,
  "limit": 100,
  "offset": 0,
  "messages": [
    {
      "id": 123,
      "sender_number": "+1234567890",
      "sender_name": "John Doe",
      "timestamp": 1234567890000,
      "received_at": "2024-01-01T12:00:00",
      "message_body": "Hello!",
      "attachments": [],
      "processed": false
    }
  ]
}
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

MIT License - feel free to use this project for any purpose.

## ⚠️ Disclaimer

This project is not affiliated with or endorsed by Signal Messenger LLC. Use at your own risk.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review logs: `sudo journalctl -u signal-controller-public -n 100`
3. Open an issue on GitHub

---

**Author**: Jan Knapen  
**Repository**: https://github.com/JanKnapen/signal-controller  
**Version**: 1.0.0
