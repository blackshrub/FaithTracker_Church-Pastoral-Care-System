#!/bin/bash

#################################################################################
# FaithTracker Update Script
# Run this after git pull to update backend and frontend
#################################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}  FaithTracker Update Script${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""

# Check if running from correct directory
if [ ! -f "backend/server.py" ]; then
    echo -e "${RED}Error: Must run from /opt/faithtracker directory${NC}"
    exit 1
fi

# Pull latest code
echo -e "${BLUE}[1/6]${NC} Pulling latest code from GitHub..."
git pull origin main

# Update backend
echo -e "${BLUE}[2/6]${NC} Updating backend..."
cd backend
source venv/bin/activate
pip install -r requirements.txt --quiet
cd ..

# Update frontend
echo -e "${BLUE}[3/6]${NC} Updating frontend..."
cd frontend
yarn install --silent
yarn build --silent
cd ..

# Restart backend service
echo -e "${BLUE}[4/6]${NC} Restarting backend service..."
sudo systemctl restart faithtracker-backend

# Restart nginx
echo -e "${BLUE}[5/6]${NC} Restarting nginx..."
sudo systemctl restart nginx

# Verify services
echo -e "${BLUE}[6/6]${NC} Verifying services..."
sleep 2

BACKEND_STATUS=$(sudo systemctl is-active faithtracker-backend)
NGINX_STATUS=$(sudo systemctl is-active nginx)

if [ "$BACKEND_STATUS" = "active" ]; then
    echo -e "${GREEN}✓ Backend: Running${NC}"
else
    echo -e "${RED}✗ Backend: Not running${NC}"
fi

if [ "$NGINX_STATUS" = "active" ]; then
    echo -e "${GREEN}✓ Nginx: Running${NC}"
else
    echo -e "${RED}✗ Nginx: Not running${NC}"
fi

echo ""
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  Update Complete!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Visit your website"
echo "2. Hard refresh browser (Ctrl+Shift+R)"
echo "3. Test main features"
echo ""
echo -e "${BLUE}View backend logs:${NC} sudo journalctl -u faithtracker-backend -f"
echo -e "${BLUE}View nginx logs:${NC} sudo tail -f /var/log/nginx/error.log"
echo ""
