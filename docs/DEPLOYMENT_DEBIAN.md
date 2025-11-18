# 🚀 FaithTracker Deployment Guide for Debian 12

Complete, step-by-step deployment guide for a **fresh Debian 12 server** with no control panel.

**Target Audience:** System administrators with basic Linux knowledge  
**Time Required:** 30-60 minutes  
**Difficulty:** Intermediate

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Server Setup](#server-setup)
3. [Install Dependencies](#install-dependencies)
4. [Clone Repository](#clone-repository)
5. [Configure Environment Variables](#configure-environment-variables)
6. [Backend Setup](#backend-setup)
7. [Frontend Setup](#frontend-setup)
8. [Configure Systemd Services](#configure-systemd-services)
9. [Configure Nginx](#configure-nginx)
10. [SSL/HTTPS Setup](#sslhttps-setup)
11. [Final Testing](#final-testing)
12. [Troubleshooting](#troubleshooting)
13. [Backup & Maintenance](#backup--maintenance)

---

## Prerequisites

### Server Requirements

- **OS**: Debian 12 (Bookworm) or Ubuntu 20.04+
- **RAM**: Minimum 2GB (4GB recommended)
- **Storage**: 20GB available space
- **CPU**: 2 cores minimum
- **Network**: Public IP address with open ports 80 and 443

### What You'll Need

- Root or sudo access to the server
- Domain name pointed to your server's IP (optional but recommended for SSL)
- MongoDB connection string (local or remote)
- Basic knowledge of Linux command line

### SSH Access

```bash
ssh root@your-server-ip
# Or with a user account:
ssh username@your-server-ip
```

---

## Server Setup

### 1. Update System Packages

```bash
# Update package list
sudo apt update

# Upgrade existing packages
sudo apt upgrade -y

# Install essential build tools
sudo apt install -y build-essential curl wget git
```

### 2. Create Application User (Optional but Recommended)

Running applications as root is a security risk. Create a dedicated user:

```bash
# Create user
sudo adduser faithtracker
# Press Enter to skip optional fields

# Add user to sudo group (if needed)
sudo usermod -aG sudo faithtracker

# Switch to new user
su - faithtracker
```

For the rest of this guide, we'll assume you're using the `faithtracker` user. If you prefer root, omit `sudo` from commands.

---

## Install Dependencies

### 1. Install Python 3.9+

Debian 12 comes with Python 3.11 by default. Verify:

```bash
python3 --version
# Should output: Python 3.11.x
```

If Python is not installed or version is too old:

```bash
sudo apt install -y python3 python3-pip python3-venv python3-dev
```

### 2. Install Node.js & Yarn

**Option A: Using NodeSource Repository (Recommended)**

```bash
# Install Node.js 18.x (LTS)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Verify installation
node --version
# Should output: v18.x.x

npm --version
# Should output: 9.x.x

# Install Yarn
sudo npm install -g yarn

# Verify Yarn
yarn --version
```

**Option B: Using NVM (Node Version Manager)**

```bash
# Install NVM
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash

# Reload shell
source ~/.bashrc

# Install Node.js 18 LTS
nvm install 18
nvm use 18

# Install Yarn
npm install -g yarn
```

### 3. Install MongoDB

**Option A: Install Locally**

```bash
# Import MongoDB GPG key
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg

# Add MongoDB repository
echo "deb [signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] http://repo.mongodb.org/apt/debian bookworm/mongodb-org/7.0 main" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# Update package list
sudo apt update

# Install MongoDB
sudo apt install -y mongodb-org

# Start MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod

# Verify MongoDB is running
sudo systemctl status mongod
```

**Option B: Use Remote/Managed MongoDB (MongoDB Atlas, etc.)**

If using a remote MongoDB service:
- Skip local MongoDB installation
- Note your connection string (e.g., `mongodb+srv://user:pass@cluster.mongodb.net/dbname`)

### 4. Install Nginx

```bash
sudo apt install -y nginx

# Start Nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# Verify Nginx is running
sudo systemctl status nginx
```

### 5. Install Supervisor (Process Manager)

```bash
sudo apt install -y supervisor

# Start Supervisor
sudo systemctl start supervisor
sudo systemctl enable supervisor
```

---

## Clone Repository

### 1. Choose Installation Directory

```bash
# Create directory for the application
sudo mkdir -p /opt/faithtracker
sudo chown faithtracker:faithtracker /opt/faithtracker

# Navigate to directory
cd /opt/faithtracker
```

### 2. Clone from GitHub

```bash
git clone https://github.com/YOUR-USERNAME/faithtracker.git .
# Note the trailing dot (.) to clone into current directory

# Verify files
ls -la
# You should see: backend/, frontend/, docs/, README.md, etc.
```

**If you don't have Git credentials configured:**

```bash
# For HTTPS with Personal Access Token:
git clone https://YOUR-GITHUB-USERNAME:YOUR-PERSONAL-ACCESS-TOKEN@github.com/YOUR-USERNAME/faithtracker.git .

# Or use SSH (requires SSH key setup):
git clone git@github.com:YOUR-USERNAME/faithtracker.git .
```

---

## Configure Environment Variables

### 1. Backend Environment Variables

```bash
cd /opt/faithtracker/backend

# Copy example env file
cp ../.env.example .env

# Edit with your preferred editor
nano .env
# Or: vim .env
```

**Configure the following:**

```bash
# MongoDB Connection
MONGO_URL="mongodb://localhost:27017"
# For remote MongoDB:
# MONGO_URL="mongodb+srv://user:password@cluster.mongodb.net/?retryWrites=true&w=majority"

# Database Name
DB_NAME="pastoral_care_db"

# CORS Origins (your domain)
CORS_ORIGINS="https://yourdomain.com"
# For development, use "*"

# JWT Secret (CRITICAL - MUST BE CHANGED)
# Generate a strong secret:
JWT_SECRET_KEY="YOUR-STRONG-RANDOM-SECRET-HERE"

# To generate a random secret, run:
# openssl rand -hex 32
# Then paste the output here

# Church Name
CHURCH_NAME="GKBJ"

# WhatsApp Gateway (Optional)
WHATSAPP_GATEWAY_URL="http://your-whatsapp-gateway:3001"
```

**Save and exit** (Ctrl+X, Y, Enter in nano).

### 2. Frontend Environment Variables

```bash
cd /opt/faithtracker/frontend

# Copy example env file
cp ../.env.example .env

# Edit
nano .env
```

**Configure the following:**

```bash
# Backend URL (DO NOT include /api - it's added automatically)
REACT_APP_BACKEND_URL="https://yourdomain.com"
# For development:
# REACT_APP_BACKEND_URL="http://localhost:8001"

# Development server config
WDS_SOCKET_PORT=443

# Feature flags
REACT_APP_ENABLE_VISUAL_EDITS=false
ENABLE_HEALTH_CHECK=false
```

**Save and exit**.

---

## Backend Setup

### 1. Create Python Virtual Environment

```bash
cd /opt/faithtracker/backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Verify you're in the venv (prompt should show "(venv)")
```

### 2. Install Python Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# This will install:
# - fastapi, uvicorn
# - motor (MongoDB async driver)
# - pydantic, python-jose, passlib
# - pillow, httpx
# - APScheduler
# ... and more
```

**Expected output:**
```
Successfully installed fastapi-0.104.1 uvicorn-0.24.0 motor-3.3.1 ...
```

### 3. Create MongoDB Indexes

```bash
# Still in the backend directory with venv activated
python create_indexes.py
```

**Expected output:**
```
Indexes created successfully:
- members: church_id, email, phone
- care_events: church_id, member_id, event_date
- users: email
```

### 4. Create Initial Admin User

```bash
# Start a Python interactive shell
python3

# Run the following Python code:
```

```python
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
import os
import asyncio

# Load environment
mongo_url = "mongodb://localhost:27017"  # Use your MONGO_URL
db_name = "pastoral_care_db"

# Connect to MongoDB
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

# Create password hasher
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Create admin user
async def create_admin():
    user = {
        "email": "admin@yourdomain.com",  # CHANGE THIS
        "password_hash": pwd_context.hash("admin123"),  # CHANGE THIS PASSWORD
        "name": "Admin User",
        "role": "full_admin",
        "church_id": None  # Full admin has no specific campus
    }
    
    # Check if user exists
    existing = await db.users.find_one({"email": user["email"]})
    if existing:
        print("Admin user already exists")
    else:
        await db.users.insert_one(user)
        print(f"Admin user created: {user['email']}")

# Run
asyncio.run(create_admin())
```

**Exit Python shell:**
```python
exit()
```

### 5. Test Backend Directly

```bash
# Start backend manually to test (in venv)
uvicorn server:app --host 0.0.0.0 --port 8001

# Press Ctrl+C to stop after verifying it starts without errors
```

**Expected output:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

**Test the API:**

Open another terminal and run:
```bash
curl http://localhost:8001/api/config/all
# Should return JSON with configuration data
```

---

## Frontend Setup

### 1. Install Node Dependencies

```bash
cd /opt/faithtracker/frontend

# Install packages with Yarn
yarn install

# This will install:
# - react, react-dom
# - react-router-dom
# - axios, @tanstack/react-query
# - tailwindcss, shadcn/ui components
# ... and more
```

**Expected output:**
```
success Saved lockfile.
Done in 45.67s.
```

### 2. Build Frontend for Production

```bash
# Build the React app
yarn build

# This creates an optimized production build in /build
```

**Expected output:**
```
Creating an optimized production build...
Compiled successfully.

File sizes after gzip:
  123.45 KB  build/static/js/main.abc123.js
  12.34 KB   build/static/css/main.xyz789.css

The build folder is ready to be deployed.
```

**Verify build:**
```bash
ls -lh build/
# Should show: index.html, static/ (with css/ and js/ subdirectories)
```

---

## Configure Systemd Services

We'll create a systemd service to run the FastAPI backend.

### 1. Create Backend Service File

```bash
sudo nano /etc/systemd/system/faithtracker-backend.service
```

**Paste the following:**

```ini
[Unit]
Description=FaithTracker FastAPI Backend
After=network.target mongod.service
Requires=mongod.service

[Service]
Type=simple
User=faithtracker
Group=faithtracker
WorkingDirectory=/opt/faithtracker/backend
Environment="PATH=/opt/faithtracker/backend/venv/bin"
ExecStart=/opt/faithtracker/backend/venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001 --workers 4
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=faithtracker-backend

[Install]
WantedBy=multi-user.target
```

**Save and exit** (Ctrl+X, Y, Enter).

**Explanation:**
- `User=faithtracker`: Runs as the faithtracker user (not root)
- `WorkingDirectory`: Backend directory
- `ExecStart`: Command to start Uvicorn with 4 workers
- `Restart=always`: Auto-restart on crash
- `After=mongod.service`: Waits for MongoDB to start first

### 2. Enable and Start Backend Service

```bash
# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable faithtracker-backend

# Start the service
sudo systemctl start faithtracker-backend

# Check status
sudo systemctl status faithtracker-backend
```

**Expected output:**
```
● faithtracker-backend.service - FaithTracker FastAPI Backend
     Loaded: loaded (/etc/systemd/system/faithtracker-backend.service; enabled)
     Active: active (running) since Mon 2024-01-15 10:30:00 UTC; 5s ago
   Main PID: 12345 (uvicorn)
      Tasks: 5 (limit: 4915)
     Memory: 120.5M
```

**If there are errors:**
```bash
# View logs
sudo journalctl -u faithtracker-backend -f
# Press Ctrl+C to exit
```

---

## Configure Nginx

Nginx will serve the React frontend and proxy API requests to the backend.

### 1. Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/faithtracker
```

**Paste the following:**

```nginx
# FaithTracker Nginx Configuration

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    # CHANGE "yourdomain.com" to your actual domain

    # Frontend - Serve React build
    root /opt/faithtracker/frontend/build;
    index index.html;

    # Gzip compression for better performance
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript;

    # API Requests - Proxy to Backend
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Timeouts for long-running requests
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Frontend - React Router Support
    # All non-API routes should serve index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Static Assets - Cache for 1 year
    location /static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Uploaded Files (Member Photos)
    location /uploads/ {
        alias /opt/faithtracker/backend/uploads/;
        expires 30d;
        add_header Cache-Control "public";
    }

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Max upload size (for member photos)
    client_max_body_size 10M;
}
```

**Save and exit**.

### 2. Enable Nginx Configuration

```bash
# Create symbolic link to enable site
sudo ln -s /etc/nginx/sites-available/faithtracker /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t
```

**Expected output:**
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

**If there are errors**, review your configuration file for typos.

### 3. Restart Nginx

```bash
sudo systemctl restart nginx

# Check status
sudo systemctl status nginx
```

---

## SSL/HTTPS Setup

### Using Let's Encrypt (Certbot)

**Let's Encrypt** provides free SSL certificates.

### 1. Install Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 2. Obtain SSL Certificate

```bash
# Run Certbot (it will auto-configure Nginx)
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
# CHANGE "yourdomain.com" to your actual domain

# Follow the prompts:
# - Enter your email address
# - Agree to Terms of Service (Y)
# - Share email with EFF? (your choice)
# - Redirect HTTP to HTTPS? YES (recommended)
```

**Expected output:**
```
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/yourdomain.com/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/yourdomain.com/privkey.pem
```

### 3. Verify Auto-Renewal

```bash
# Test renewal
sudo certbot renew --dry-run
```

**Expected output:**
```
Congratulations, all simulated renewals succeeded
```

Certbot automatically adds a cron job to renew certificates before they expire (every 90 days).

### 4. Verify HTTPS

Visit https://yourdomain.com in your browser. You should see a padlock icon indicating a secure connection.

---

## Final Testing

### 1. Backend API Test

```bash
# Test health check
curl https://yourdomain.com/api/config/all
```

**Expected:** JSON response with configuration data.

### 2. Login Test

```bash
# Test login with the admin user you created earlier
curl -X POST https://yourdomain.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@yourdomain.com","password":"admin123"}'
```

**Expected:** JSON response with `access_token` and `user` object.

### 3. Frontend Test

Open your browser and navigate to:
```
https://yourdomain.com
```

**You should see:**
- The FaithTracker login page
- No console errors (check browser DevTools)

**Log in with:**
- Email: `admin@yourdomain.com`
- Password: `admin123` (or whatever you set)

**After login, you should see:**
- The Dashboard page
- No errors in the console

---

## Troubleshooting

### Backend Service Won't Start

**Check logs:**
```bash
sudo journalctl -u faithtracker-backend -n 50
```

**Common issues:**
- **MongoDB not running**: `sudo systemctl start mongod`
- **Environment variable error**: Check `/opt/faithtracker/backend/.env`
- **Port 8001 in use**: `sudo lsof -i :8001` (kill conflicting process)
- **Python dependencies missing**: Rerun `pip install -r requirements.txt`

---

### Nginx 502 Bad Gateway

**Meaning:** Nginx can't connect to the backend.

**Check:**
1. Is backend service running?
   ```bash
   sudo systemctl status faithtracker-backend
   ```
2. Is backend listening on port 8001?
   ```bash
   sudo netstat -tuln | grep 8001
   ```
3. Firewall blocking connections?
   ```bash
   sudo ufw status
   # If active, allow port 8001:
   sudo ufw allow 8001
   ```

---

### Frontend Shows Blank Page

**Check browser console** (F12 → Console tab):
- **"Failed to load resource"**: Backend API not responding
- **CORS error**: Check `CORS_ORIGINS` in backend `.env`
- **404 errors**: Check Nginx configuration for `try_files` directive

**Check frontend build:**
```bash
ls /opt/faithtracker/frontend/build/
# Should contain: index.html, static/
```

**Rebuild frontend:**
```bash
cd /opt/faithtracker/frontend
yarn build
sudo systemctl restart nginx
```

---

### SSL Certificate Errors

**"Certificate not trusted":**
- Wait a few minutes after obtaining certificate
- Clear browser cache
- Check certificate validity:
  ```bash
  sudo certbot certificates
  ```

**Certificate renewal failed:**
```bash
# Manual renewal
sudo certbot renew --force-renewal
```

---

### Can't Log In

**"Invalid credentials":**
- Verify admin user exists in MongoDB:
  ```bash
  mongosh
  use pastoral_care_db
  db.users.find({ email: "admin@yourdomain.com" })
  ```
- Recreate admin user (see [Backend Setup](#backend-setup) step 4)

**"Network Error":**
- Check backend is running: `sudo systemctl status faithtracker-backend`
- Check API endpoint: `curl http://localhost:8001/api/auth/login`

---

## Backup & Maintenance

### Database Backup

**Create a backup script:**

```bash
sudo nano /opt/faithtracker/backup.sh
```

**Paste:**
```bash
#!/bin/bash

# Backup directory
BACKUP_DIR="/opt/faithtracker/backups"
mkdir -p $BACKUP_DIR

# Backup filename with date
DATE=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_FILE="$BACKUP_DIR/faithtracker_backup_$DATE.gz"

# MongoDB dump
mongodump --db=pastoral_care_db --archive=$BACKUP_FILE --gzip

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE"
```

**Make executable:**
```bash
sudo chmod +x /opt/faithtracker/backup.sh
```

**Schedule daily backups (3 AM):**
```bash
sudo crontab -e
# Add this line:
0 3 * * * /opt/faithtracker/backup.sh
```

### Restore from Backup

```bash
# Restore from a specific backup file
mongorestore --db=pastoral_care_db --archive=/opt/faithtracker/backups/faithtracker_backup_2024-01-15_03-00-00.gz --gzip
```

---

### Update Application

**When you push new code to GitHub:**

```bash
cd /opt/faithtracker

# Pull latest code
git pull origin main

# Update backend
cd backend
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart faithtracker-backend

# Update frontend
cd ../frontend
yarn install
yarn build
sudo systemctl restart nginx

# Check everything is running
sudo systemctl status faithtracker-backend
sudo systemctl status nginx
```

---

### Monitor Logs

**Backend logs:**
```bash
# Real-time logs
sudo journalctl -u faithtracker-backend -f

# Last 100 lines
sudo journalctl -u faithtracker-backend -n 100
```

**Nginx access logs:**
```bash
sudo tail -f /var/log/nginx/access.log
```

**Nginx error logs:**
```bash
sudo tail -f /var/log/nginx/error.log
```

---

### Security Hardening

**1. Firewall (UFW):**

```bash
# Enable firewall
sudo ufw enable

# Allow SSH
sudo ufw allow ssh

# Allow HTTP & HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Check status
sudo ufw status
```

**2. Fail2Ban (Brute Force Protection):**

```bash
# Install
sudo apt install -y fail2ban

# Enable
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

**3. Regular Updates:**

```bash
# Weekly security updates
sudo apt update
sudo apt upgrade -y
```

---

### Performance Tuning

**1. Increase Uvicorn Workers (if server has 4+ CPU cores):**

Edit `/etc/systemd/system/faithtracker-backend.service`:
```ini
ExecStart=/opt/faithtracker/backend/venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001 --workers 8
```

Restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart faithtracker-backend
```

**2. Enable Nginx Caching:**

Add to Nginx configuration:
```nginx
# Add at top of server block
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m max_size=1g inactive=60m use_temp_path=off;

# Add in location /api/ block
proxy_cache my_cache;
proxy_cache_valid 200 5m;
```

---

## Production Checklist

Before going live, verify:

- [ ] Backend service running: `sudo systemctl status faithtracker-backend`
- [ ] Frontend built: `ls /opt/faithtracker/frontend/build/`
- [ ] Nginx running: `sudo systemctl status nginx`
- [ ] SSL certificate valid: Visit https://yourdomain.com
- [ ] Login works with admin credentials
- [ ] Database backup scheduled (cron job)
- [ ] Firewall enabled and configured
- [ ] Environment variables secure (strong JWT secret)
- [ ] CORS configured correctly (production domain only)
- [ ] Monitoring set up (optional: Uptime Robot, New Relic, etc.)

---

## Getting Help

**Log locations:**
- Backend: `sudo journalctl -u faithtracker-backend`
- Nginx: `/var/log/nginx/error.log`
- System: `/var/log/syslog`

**Useful commands:**
```bash
# Service status
sudo systemctl status faithtracker-backend nginx mongod

# Restart all services
sudo systemctl restart faithtracker-backend nginx

# Check disk space
df -h

# Check memory usage
free -h

# Check process list
ps aux | grep -E "uvicorn|nginx|mongod"
```

**Community Support:**
- GitHub Issues: [github.com/YOUR-USERNAME/faithtracker/issues]
- Email: support@yourdomain.com

---

**End of Deployment Guide**

Your FaithTracker application should now be fully deployed and accessible via HTTPS! 🎉

For more information:
- [Features Guide](/docs/FEATURES.md)
- [API Reference](/docs/API.md)
- [Codebase Structure](/docs/STRUCTURE.md)
