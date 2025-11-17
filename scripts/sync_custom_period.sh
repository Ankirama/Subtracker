#!/bin/bash
#
# Custom Email Sync Script
# Syncs emails from a custom time period with configurable rate limiting
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Custom Email Sync ===${NC}"
echo ""

# Get mailbox ID
read -p "Enter your mailbox ID: " MAILBOX_ID

if [ -z "$MAILBOX_ID" ]; then
    echo -e "${RED}Error: Mailbox ID is required${NC}"
    exit 1
fi

# Show period options
echo ""
echo "Select sync period:"
echo "  1) Last 7 days"
echo "  2) Last 30 days (default)"
echo "  3) Last 90 days (3 months)"
echo "  4) Last 180 days (6 months)"
echo "  5) Last 365 days (1 year)"
echo "  6) Custom (specify days)"
read -p "Choose option (1-6): " PERIOD_CHOICE

case $PERIOD_CHOICE in
    1)
        PERIOD="7days"
        DESCRIPTION="Last 7 days"
        ;;
    2)
        PERIOD="30days"
        DESCRIPTION="Last 30 days"
        ;;
    3)
        PERIOD="90days"
        DESCRIPTION="Last 90 days (3 months)"
        ;;
    4)
        PERIOD="180days"
        DESCRIPTION="Last 180 days (6 months)"
        ;;
    5)
        PERIOD="365days"
        DESCRIPTION="Last 365 days (1 year)"
        ;;
    6)
        read -p "Enter number of days: " CUSTOM_DAYS
        PERIOD="${CUSTOM_DAYS}days"
        DESCRIPTION="Last ${CUSTOM_DAYS} days"
        ;;
    *)
        echo -e "${RED}Invalid choice, using default (30 days)${NC}"
        PERIOD="30days"
        DESCRIPTION="Last 30 days"
        ;;
esac

# Optional: Configure rate limiting
echo ""
read -p "Configure OpenAI rate limiting? (yes/no) [no]: " CONFIGURE_RATE_LIMIT
CONFIGURE_RATE_LIMIT=${CONFIGURE_RATE_LIMIT:-no}

if [ "$CONFIGURE_RATE_LIMIT" = "yes" ]; then
    echo ""
    echo -e "${YELLOW}Current rate limiting settings:${NC}"
    echo "  - Delay between API calls: 1.0 seconds"
    echo "  - Max requests per minute: 60"
    echo ""
    read -p "Delay between OpenAI API calls (seconds) [1.0]: " DELAY
    DELAY=${DELAY:-1.0}

    read -p "Max requests per minute [60]: " MAX_REQUESTS
    MAX_REQUESTS=${MAX_REQUESTS:-60}

    echo ""
    echo -e "${YELLOW}Note: Rate limiting settings will need to be updated in .env file${NC}"
    echo "  OPENAI_REQUEST_DELAY_SECONDS=$DELAY"
    echo "  OPENAI_MAX_REQUESTS_PER_MINUTE=$MAX_REQUESTS"
    echo ""
fi

# Confirm before starting
echo ""
echo -e "${BLUE}=== Sync Configuration ===${NC}"
echo "  Mailbox ID: $MAILBOX_ID"
echo "  Period: $DESCRIPTION"
echo "  Date filter: $PERIOD"
if [ "$CONFIGURE_RATE_LIMIT" = "yes" ]; then
    echo "  Rate limiting: $DELAY seconds delay, $MAX_REQUESTS max req/min"
fi
echo ""
read -p "Start email sync? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Sync cancelled"
    exit 0
fi

# Get authentication token
echo ""
echo -e "${YELLOW}Authenticating...${NC}"

# Try to get token from environment first
if [ -z "$TOKEN" ]; then
    read -p "Enter your email: " EMAIL
    read -sp "Enter your password: " PASSWORD
    echo ""

    TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
        | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

    if [ -z "$TOKEN" ]; then
        echo -e "${RED}Authentication failed${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ Authenticated${NC}"

# Trigger email sync
echo ""
echo -e "${YELLOW}Starting email sync for $DESCRIPTION...${NC}"
echo "This may take a while depending on the number of emails..."
echo ""

RESPONSE=$(curl -s -X POST "http://localhost:8000/api/mailboxes/${MAILBOX_ID}/sync" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"force_full_sync\": false, \"date_filter\": \"$PERIOD\"}")

echo -e "${GREEN}✓ Sync started${NC}"
echo ""
echo "Response: $RESPONSE"
echo ""
echo -e "${BLUE}Tips:${NC}"
echo "  - Check sync status in the web UI"
echo "  - Monitor Celery logs: docker logs -f subscriptions_celery"
echo "  - Large syncs (365 days) may take 10-30 minutes with rate limiting"
echo "  - OpenAI rate limits: ~60 requests per minute (adjustable in .env)"
echo ""
echo -e "${GREEN}=== Sync Initiated ===${NC}"
