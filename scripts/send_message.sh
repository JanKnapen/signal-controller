#!/bin/bash
#
# Script to send a Signal message via the private API
# Usage: ./send_message.sh <recipient> <message>
#

set -e

# Load environment variables
if [ -f /etc/signal-controller/.env ]; then
    source /etc/signal-controller/.env
fi

API_KEY="${SIGNAL_API_KEY:-CHANGE_ME}"
API_URL="${SIGNAL_PRIVATE_API_URL:-http://localhost:9000}"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <recipient> <message> [attachment]"
    echo "Example: $0 +1234567890 'Hello from SignalController'"
    exit 1
fi

RECIPIENT="$1"
MESSAGE="$2"
ATTACHMENT="${3:-}"

# Build JSON payload
if [ -z "$ATTACHMENT" ]; then
    JSON_PAYLOAD=$(jq -n \
        --arg to "$RECIPIENT" \
        --arg msg "$MESSAGE" \
        '{to: $to, message: $msg}')
else
    JSON_PAYLOAD=$(jq -n \
        --arg to "$RECIPIENT" \
        --arg msg "$MESSAGE" \
        --arg att "$ATTACHMENT" \
        '{to: $to, message: $msg, attachment: $att}')
fi

# Send request
echo "Sending message to $RECIPIENT..."
RESPONSE=$(curl -s -X POST "$API_URL/send" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d "$JSON_PAYLOAD")

echo "Response: $RESPONSE"

# Check if successful
if echo "$RESPONSE" | jq -e '.status == "sent"' > /dev/null; then
    echo "✓ Message sent successfully"
    exit 0
else
    echo "✗ Failed to send message"
    exit 1
fi
