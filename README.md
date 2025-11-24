# SignalController

Send and receive Signal messages via REST API.

## Installation

```bash
cd /opt
git clone https://github.com/JanKnapen/signal-controller.git
cd signal-controller
sudo ./scripts/install.sh
```

## Setup

1. Register Signal:
```bash
sudo ./scripts/register_signal.sh
```

2. Create `/etc/signal-controller/.env`:
```
SIGNAL_PHONE_NUMBER=+1234567890
SIGNAL_API_KEY=your_secure_key
PRIVATE_API_WHITELIST=127.0.0.1,192.168.1.100
```

3. Point Cloudflare Tunnel to `http://YOUR_VM_IP:8888`

4. Start:
```bash
sudo systemctl enable --now signal-cli signal-controller-public signal-controller-private
```

## Usage

**Note:** Private API (port 9000) uses IP whitelisting. Only IPs in `PRIVATE_API_WHITELIST` can access it.

Send:
```bash
curl -X POST http://localhost:9000/send -H "Content-Type: application/json" -H "X-API-Key: KEY" -d '{"to": "+1234567890", "message": "Hi"}'
```

Get messages:
```bash
curl http://localhost:9000/messages -H "X-API-Key: KEY"
```

## License

MIT
