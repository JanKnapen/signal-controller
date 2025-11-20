# SignalController - Project Structure

```
SignalController/
│
├── 📄 README.md                    # Complete documentation
├── 📄 QUICKSTART.md                # Fast installation guide
├── 📄 SECURITY.md                  # Security hardening guide
├── 📄 .env.example                 # Environment template
├── 📄 .gitignore                   # Git ignore rules
│
├── 🔧 backend/                     # Python FastAPI application
│   ├── main.py                     # Main application (public + private interfaces)
│   ├── config.py                   # Configuration management
│   ├── signal_client.py            # signal-cli REST API wrapper
│   └── requirements.txt            # Python dependencies
│
├── 💾 database/                    # Database layer
│   ├── db.py                       # SQLite database operations
│   └── init_db.py                  # Schema initialization script
│
├── 📜 scripts/                     # Utility scripts
│   ├── install.sh                  # Automated installation
│   ├── register_signal.sh          # Signal number registration
│   ├── send_message.sh             # Send message via API
│   └── query_messages.sh           # Query stored messages
│
├── 🔄 systemd/                     # System service files
│   ├── signal-cli.service          # signal-cli daemon
│   ├── signal-controller-public.service    # Public webhook interface
│   └── signal-controller-private.service   # Private API interface
│
├── 🌐 nginx/                       # Web server configuration
│   └── signal-controller.conf      # Nginx reverse proxy + rate limiting
│
└── 🐳 docker/                      # Docker deployment (optional)
    ├── Dockerfile                  # Container image
    ├── docker-compose.yml          # Multi-container setup
    └── .env.example                # Docker environment template
```

## 🔀 Architecture Flow

```
Internet
   │
   ├──[HTTPS:443]──► Nginx ──► [HTTPS:8443] Public Interface (FastAPI)
   │                   │                           │
   │                   │                           ├─► Parse webhook
   │                   │                           ├─► Store in SQLite
   │                   │                           └─► Log event
   │                   │
   │              Rate Limiting
   │              DoS Protection
   │
   
Internal Network
   │
   └──[HTTP:9000]──► Private Interface (FastAPI)
                          │
                          ├─► Authentication (API Key)
                          ├─► Send messages ──► signal-cli REST [8080]
                          ├─► Query messages ──► SQLite Database
                          └─► Statistics


signal-cli REST API [localhost:8080]
   │
   ├─► Manages Signal protocol
   ├─► Sends/receives messages
   └─► Connected to +YOUR_PHONE_NUMBER
```

## 📊 Data Flow

### Incoming Message Flow
```
Signal Network
    │
    ├─► signal-cli receives message
    │
    ├─► signal-cli webhook POST to /webhook/signal
    │
    ├─► Public Interface parses message
    │       ├─ sender_number
    │       ├─ sender_name
    │       ├─ timestamp
    │       ├─ message_body
    │       └─ attachments
    │
    └─► Store in SQLite database
            ├─ messages table
            └─ conversations table
```

### Outgoing Message Flow
```
API Client (with API Key)
    │
    ├─► POST /send to Private Interface
    │       {
    │         "to": "+1234567890",
    │         "message": "Hello"
    │       }
    │
    ├─► Validate API Key
    │
    ├─► Private Interface calls signal-cli REST API
    │
    ├─► signal-cli sends via Signal protocol
    │
    └─► Return success/failure
```

## 🔐 Security Layers

```
Layer 1: Network (Firewall)
    ├─ Port 443: HTTPS (public webhook)
    ├─ Port 80: HTTP redirect to HTTPS
    ├─ Port 9000: BLOCKED from internet
    └─ Port 8080: signal-cli (localhost only)

Layer 2: Nginx
    ├─ Rate limiting (10 req/sec)
    ├─ Connection limiting
    ├─ TLS 1.2+ only
    ├─ Security headers (HSTS, X-Frame-Options, etc.)
    └─ Request size limits

Layer 3: Application
    ├─ API Key authentication (private interface)
    ├─ Input validation
    ├─ SQL injection protection (parameterized queries)
    └─ Separate interfaces (public can't send)

Layer 4: System
    ├─ Non-root user (signal)
    ├─ systemd security features
    ├─ Minimal file system access
    └─ Resource limits
```

## 📈 Database Schema

```sql
messages
├── id (PK)
├── sender_number
├── sender_name
├── timestamp
├── received_at
├── message_body
├── attachments (JSON)
└── raw_data (JSON)

conversations
├── id (PK)
├── contact_number (UNIQUE)
├── contact_name
├── last_message_at
├── message_count
└── created_at

sent_messages
├── id (PK)
├── recipient
├── message_body
├── attachment_path
├── sent_at
├── status
└── error_message
```

## 🚀 Deployment Options

### Option 1: Native Installation (Recommended)
- systemd services
- Direct on Proxmox VM
- Best performance
- See: QUICKSTART.md

### Option 2: Docker
- Containerized deployment
- Easier management
- Portable
- See: docker/docker-compose.yml

### Option 3: Hybrid
- signal-cli in Docker
- SignalController native
- Flexibility

## 🔄 Service Dependencies

```
signal-cli.service (must start first)
    │
    ├──► signal-controller-public.service
    │
    └──► signal-controller-private.service
```

## 📞 API Endpoints

### Public Interface (Port 8443)
```
POST /webhook/signal    # Receive messages from signal-cli
GET  /health           # Health check
```

### Private Interface (Port 9000)
```
POST /send             # Send a message (requires API key)
GET  /messages         # List messages (requires API key)
GET  /messages/{id}    # Get specific message (requires API key)
GET  /stats            # Get statistics (requires API key)
GET  /health           # Health check
```

## 🛠️ Configuration Files

```
/etc/signal-controller/.env          # Main configuration
/etc/systemd/system/signal-cli.service
/etc/systemd/system/signal-controller-public.service
/etc/systemd/system/signal-controller-private.service
/etc/nginx/sites-available/signal-controller.conf
/var/lib/signal-controller/          # Data directory
/var/log/signal-controller/          # Log directory
/opt/signal-controller/              # Application directory
```

## 📦 Key Dependencies

### System
- Python 3.8+
- Java 17 (for signal-cli)
- SQLite 3
- Nginx
- systemd

### Python Packages
- FastAPI (web framework)
- Uvicorn (ASGI server)
- httpx (HTTP client)
- Pydantic (data validation)
- aiosqlite (async SQLite)

### External
- signal-cli v0.13.1+ (Signal protocol)
- Let's Encrypt (SSL certificates)

## 🎯 Use Cases

✅ **Home Automation**
- Receive alerts from home systems
- Send commands via Signal

✅ **Monitoring & Alerts**
- Server monitoring notifications
- Application alerts

✅ **Bot Development**
- Build Signal bots
- Automated responses

✅ **Message Archival**
- Store Signal message history
- Search and query messages

✅ **Integration Platform**
- Connect Signal to other services
- Webhook forwarding

## 📈 Scalability

**Current Capacity:**
- ~1000 messages/day: ✅ Excellent
- ~10,000 messages/day: ✅ Good (monitor disk space)
- ~100,000+ messages/day: ⚠️ Consider PostgreSQL

**Scaling Options:**
1. Increase rate limits
2. Add Redis caching
3. Switch to PostgreSQL
4. Add message queue (RabbitMQ)
5. Multiple signal-cli instances

## 🔍 Monitoring Points

- Service health (systemd status)
- Database size
- Message throughput
- Error rates
- API latency
- Disk space
- Memory usage

## 📚 Documentation Index

1. **QUICKSTART.md** - Get started in 30 minutes
2. **README.md** - Complete guide
3. **SECURITY.md** - Security hardening
4. **STRUCTURE.md** (this file) - Project overview
5. **Code comments** - Inline documentation

---

**Total Lines of Code:** ~2,500  
**Programming Language:** Python  
**Framework:** FastAPI  
**Database:** SQLite  
**Deployment:** systemd + Docker  
**License:** MIT
