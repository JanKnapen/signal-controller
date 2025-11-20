#!/bin/bash
#
# Script to query received messages via the private API
# Usage: ./query_messages.sh [options]
#

set -e

# Load environment variables
if [ -f /etc/signal-controller/.env ]; then
    source /etc/signal-controller/.env
fi

API_KEY="${SIGNAL_API_KEY:-CHANGE_ME}"
API_URL="${SIGNAL_PRIVATE_API_URL:-http://localhost:9000}"

# Parse arguments
LIMIT=10
OFFSET=0
SENDER=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --limit)
            LIMIT="$2"
            shift 2
            ;;
        --offset)
            OFFSET="$2"
            shift 2
            ;;
        --sender)
            SENDER="$2"
            shift 2
            ;;
        --stats)
            STATS=1
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--limit N] [--offset N] [--sender PHONE] [--stats]"
            exit 1
            ;;
    esac
done

# Get statistics if requested
if [ "$STATS" = "1" ]; then
    echo "Fetching statistics..."
    curl -s -X GET "$API_URL/stats" \
        -H "X-API-Key: $API_KEY" | jq '.'
    exit 0
fi

# Build query parameters
PARAMS="limit=$LIMIT&offset=$OFFSET"
if [ -n "$SENDER" ]; then
    PARAMS="$PARAMS&sender=$SENDER"
fi

# Query messages
echo "Fetching messages..."
RESPONSE=$(curl -s -X GET "$API_URL/messages?$PARAMS" \
    -H "X-API-Key: $API_KEY")

echo "$RESPONSE" | jq '.'

# Summary
COUNT=$(echo "$RESPONSE" | jq '.count')
echo ""
echo "Retrieved $COUNT messages"
