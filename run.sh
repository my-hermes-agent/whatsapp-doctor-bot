#!/usr/bin/env bash
# WhatsApp Doctor Bot — Startup Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

MODE="${1:-prod}"

echo -e "${CYAN}🏥 Nellore Doctor Bot${NC}"

# Load .env if present
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo -e "${GREEN}✅ Loaded .env${NC}"
fi

# Initialize DB if needed
if [ ! -f instance/doctorbot.db ]; then
    echo -e "${CYAN}📦 Initializing database...${NC}"
    flask --app app init-db
    echo -e "${GREEN}✅ Database ready${NC}"
fi

if [ "$MODE" = "dev" ]; then
    echo -e "${CYAN}🔧 Starting in DEV mode (Flask debug)...${NC}"
    export TWILIO_DEV_MODE=1
    flask --app app run --port 5000 --debug
else
    echo -e "${CYAN}🚀 Starting in PRODUCTION mode (Gunicorn)...${NC}"
    PORT="${PORT:-5000}"
    WORKERS="${WORKERS:-2}"
    gunicorn wsgi:app \
        --bind "0.0.0.0:$PORT" \
        --workers "$WORKERS" \
        --timeout 120 \
        --access-logfile - \
        --error-logfile -
fi
