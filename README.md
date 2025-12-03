# FaithTracker Pastoral Care System

**FaithTracker** is a complete pastoral care management system for churches. It helps pastors and staff track birthdays, hospital visits, grief support, financial aid, and more - all from one easy-to-use dashboard.

![Status](https://img.shields.io/badge/status-production--ready-brightgreen)
![Platform](https://img.shields.io/badge/platform-Web%20%2B%20Mobile-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## What Can FaithTracker Do?

- **Track Birthdays** - Never miss a member's birthday again
- **Grief Support** - 6-stage follow-up system (7 days, 14 days, 1 month, 3 months, 6 months, 1 year)
- **Hospital Visits** - Track hospital stays with 3-stage follow-ups
- **Financial Aid** - Manage one-time and recurring aid with scheduling
- **Member Engagement** - See who's active, at-risk, or disconnected
- **Multiple Campuses** - Perfect for churches with multiple locations
- **Works on Phone & Computer** - Web app + Native mobile app (iOS & Android)

---

## Quick Start - Choose Your Installation Method

### Option 1: Docker Installation (Recommended - Easiest!)

Best for: Most users. Works on any Linux server.

**What you need before starting:**
- A Linux server (Ubuntu, Debian, or any Linux with Docker)
- A domain name (like `faithtracker.yourchurch.com`)
- Your domain pointing to your server's IP address

**Step-by-Step Instructions:**

**Step 1: Connect to your server**
Open a terminal and SSH into your server:
```bash
ssh root@your-server-ip
```

**Step 2: Install Docker (skip if already installed)**
```bash
curl -fsSL https://get.docker.com | bash
```

**Step 3: Download FaithTracker**
```bash
git clone https://github.com/tesarfrr/FaithTracker_Church-Pastoral-Care-System.git
cd FaithTracker_Church-Pastoral-Care-System
```

**Step 4: Run the Installer**
```bash
sudo bash docker-install.sh
```

**Step 5: Answer the Questions**
The installer will ask you:
| Question | Example Answer |
|----------|----------------|
| Your domain | `faithtracker.mychurch.org` |
| Your email | `pastor@mychurch.org` |
| Admin email | `admin@mychurch.org` |
| Admin password | `SecurePassword123` |
| Church name | `My Church` |

**Step 6: Wait**
The installer builds everything. This takes about 5-10 minutes.

**Done!**
- Your website: `https://yourdomain.com`
- API docs: `https://api.yourdomain.com/docs`

---

### Option 2: Traditional Installation (Without Docker)

Best for: Servers where you can't use Docker, or prefer manual control.

**What you need before starting:**
- Ubuntu 20.04+ or Debian 11+ server
- A domain name pointing to your server

**One-Command Installation:**
```bash
wget https://raw.githubusercontent.com/tesarfrr/FaithTracker_Church-Pastoral-Care-System/main/install.sh -O install.sh && chmod +x install.sh && sudo ./install.sh
```

**What the installer does:**
1. Checks if your server has enough resources
2. Installs: Python, Node.js, MongoDB, Nginx
3. Asks for your settings (domain, admin credentials)
4. Sets up SSL/HTTPS security
5. Starts everything

---

## After Installation: How to Update

Updating is easy! FaithTracker automatically backs up before updating, so you can always go back if something goes wrong.

### Docker Update
```bash
cd /path/to/FaithTracker
git pull origin main
docker compose build --no-cache
docker compose up -d
```

### Traditional Update
```bash
cd /path/to/FaithTracker
git pull origin main
sudo bash update.sh
```

### If Something Goes Wrong
Roll back to the previous version:
```bash
sudo bash update.sh --rollback
```

---

## Mobile App (iOS & Android)

FaithTracker includes a native mobile app built with React Native and Expo.

### Mobile App Features
- Dashboard with today's tasks at a glance
- Member list with search
- Create care events (birthdays, grief, hospital, financial aid)
- Member profiles with complete care history
- Works offline (syncs when connected)

### For Developers: Running the Mobile App
```bash
cd mobile
yarn install
yarn start
```

Then scan the QR code with Expo Go app on your phone.

---

## Setting Up Your Domain (Important!)

Before installing, you need to point your domain to your server.

### Step 1: Find Your Server's IP
Run this on your server:
```bash
curl -4 ifconfig.me
```
Write down the IP address (like `123.45.67.89`).

### Step 2: Add DNS Records
Go to your domain registrar (GoDaddy, Namecheap, Cloudflare, etc.) and add these records:

| Type | Name | Value | What it does |
|------|------|-------|--------------|
| A | @ | YOUR_SERVER_IP | Points `yourdomain.com` to your server |
| A | api | YOUR_SERVER_IP | Points `api.yourdomain.com` to your server |
| A | traefik | YOUR_SERVER_IP | (Optional) For Traefik dashboard |

### Step 3: Wait for DNS
DNS changes can take 5 minutes to 24 hours. Usually 15-30 minutes.

### Step 4: Verify It's Working
```bash
dig yourdomain.com +short
dig api.yourdomain.com +short
```
Both should show your server's IP.

---

## All Features

### For Pastors & Staff
| Feature | What It Does |
|---------|--------------|
| Smart Dashboard | Shows today's tasks, overdue items, and stats |
| Birthday Tracking | Automatic reminders with age calculation |
| Grief Support | 6 follow-up stages over one year |
| Hospital Visits | 3 follow-up stages (3, 7, 14 days) |
| Financial Aid | One-time or recurring payments with scheduling |
| Member Search | Find anyone instantly by name or phone |
| Activity Log | Complete history of who did what |

### For Administrators
| Feature | What It Does |
|---------|--------------|
| Multi-Campus | Manage multiple church locations |
| User Roles | Admin, Campus Admin, and Pastor roles |
| Bulk Import | Upload members from CSV/Excel |
| Analytics | Charts and statistics |
| Bilingual | English and Indonesian (Bahasa) |

### Care Event Types
| Event Type | Description |
|------------|-------------|
| Birthday | Automated tracking with age calculation |
| Grief & Loss | 6 follow-ups: 1 week, 2 weeks, 1 month, 3 months, 6 months, 1 year |
| Accident/Illness | 3 follow-ups: 3 days, 7 days, 14 days |
| Financial Aid | One-time or scheduled (weekly, monthly, annually) |
| Childbirth | New baby celebrations |
| New House | Housewarming visits |
| Regular Contact | Scheduled check-ins |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | FastAPI (Python 3.11), MongoDB 7.0, Granian (Rust ASGI server) |
| **Performance** | msgspec (fast JSON), Brotli compression, HTTP/3 (QUIC) |
| **Frontend** | React 19 + React Compiler, Vite, TanStack Query, Tailwind CSS, Shadcn/UI |
| **Mobile** | React Native, Expo, NativeWind |
| **Infrastructure** | Docker, Traefik v3.6, Let's Encrypt |
| **Caching** | In-memory TTL cache, PWA service worker, MongoDB connection pooling |

---

## Troubleshooting

### Problem: SSL Certificate Errors
**Solution:** Wait 1-2 minutes. Let's Encrypt needs time to issue certificates.

### Problem: Can't Access Website
**Solutions:**
1. Check firewall: `sudo ufw allow 80,443/tcp`
2. Make sure DNS points to your server
3. Check services:
   - Docker: `docker compose ps`
   - Traditional: `sudo systemctl status faithtracker-backend nginx`

### Problem: Seeing Error Messages
**View the logs:**
- Docker: `docker compose logs -f backend`
- Traditional: `tail -f /var/log/faithtracker/backend.err.log`

### Problem: Need to Roll Back
```bash
sudo bash update.sh --rollback
```
This restores the previous version.

---

## Management Commands

### Docker Commands
```bash
docker compose ps              # See what's running
docker compose logs -f         # Watch live logs
docker compose logs -f backend # Watch backend logs only
docker compose restart         # Restart everything
docker compose down            # Stop everything
docker compose up -d --build   # Rebuild and start
```

### Traditional Commands
```bash
sudo systemctl status faithtracker-backend  # Check backend status
sudo systemctl restart faithtracker-backend # Restart backend
sudo systemctl status nginx                 # Check web server
tail -f /var/log/faithtracker/backend.out.log  # Watch logs
```

---

## Project Structure

```
FaithTracker/
├── backend/           # Python API server
│   ├── server.py      # Main API file
│   └── requirements.txt
├── frontend/          # React web app
│   ├── src/
│   │   ├── pages/     # Dashboard, Members, etc.
│   │   └── locales/   # English + Indonesian
│   └── package.json
├── mobile/            # React Native mobile app
│   ├── app/           # Mobile screens
│   ├── components/    # Mobile UI components
│   └── package.json
├── docker-compose.yml # Docker setup
├── install.sh         # Traditional installer
├── update.sh          # Update script
└── docker-install.sh  # Docker installer
```

---

## API Documentation

After installation, you can explore the API:
- **Interactive Docs:** `https://api.yourdomain.com/docs`
- **Alternative Docs:** `https://api.yourdomain.com/redoc`

### Quick API Example
```bash
# Login and get a token
curl -X POST https://api.yourdomain.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@church.org", "password": "yourpassword"}'

# Use the token to get members
curl https://api.yourdomain.com/members \
  -H "Authorization: Bearer YOUR_TOKEN"
```

See [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) for complete reference.

---

## Language Support

FaithTracker is fully translated in:
- **English** - Complete
- **Bahasa Indonesia** - Complete

Translation files are in `frontend/src/locales/`.

---

## Performance Features

FaithTracker is optimized for speed and efficiency:

| Optimization | Benefit |
|-------------|---------|
| **Granian ASGI Server** | Rust-based, 10-15% faster than Uvicorn |
| **msgspec Serialization** | Faster than orjson, 30-50% lower memory |
| **Brotli Compression** | 15-25% smaller responses than gzip |
| **HTTP/3 (QUIC)** | Lower latency, especially on mobile networks |
| **React Compiler** | Automatic memoization, no manual optimization |
| **Route Loaders** | Parallel data prefetching during navigation |
| **PWA Caching** | Offline-capable, instant repeat loads |
| **MongoDB Pooling** | 50 connections, optimized for concurrent users |
| **Aggregation Pipelines** | Single queries instead of N+1 patterns |

---

## Security Features

- **Encrypted Passwords** - bcrypt hashing
- **Secure Tokens** - JWT authentication
- **HTTPS** - Free SSL certificates with Let's Encrypt
- **HTTP/3** - Modern secure transport protocol
- **Brotli/Gzip** - Response compression
- **Rate Limiting** - Prevents brute-force attacks
- **Data Isolation** - Each campus only sees their data
- **Audit Trail** - All actions are logged with timestamps
- **Fernet Encryption** - API credentials encrypted at rest

---

## Need Help?

- **GitHub Issues:** [Report a bug or request a feature](https://github.com/tesarfrr/FaithTracker_Church-Pastoral-Care-System/issues)
- **Documentation:** Check the `/docs` folder

---

## Contributing

Want to help improve FaithTracker?

1. Fork the repository
2. Create a branch: `git checkout -b my-feature`
3. Make changes and commit: `git commit -m 'Add feature'`
4. Push: `git push origin my-feature`
5. Open a Pull Request

---

## License

MIT License - Use it freely for your church!

---

**Built with love for churches worldwide**
