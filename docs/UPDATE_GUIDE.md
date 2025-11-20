# Update & Deployment Guide

Step-by-step guide for updating your production FaithTracker installation after code changes.

---

## Quick Update Commands

### After `git pull` - Full Update (Backend + Frontend)

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

# Verify
sudo systemctl status faithtracker-backend
sudo systemctl status nginx
```

---

## Detailed Update Workflow

### Step 1: Pull Latest Code

```bash
cd /opt/faithtracker
git pull origin main
```

**Check what changed:**
```bash
git log -3  # See last 3 commits
git diff HEAD~1  # See changes
```

---

### Step 2: Update Backend (If Python Code Changed)

**When to update backend:**
- Changes in `backend/` folder
- New Python packages in requirements.txt
- Database model changes

**Commands:**
```bash
cd /opt/faithtracker/backend

# Activate virtual environment
source venv/bin/activate

# Update Python packages
pip install -r requirements.txt

# If database migration needed (rare)
python create_performance_indexes.py  # If new indexes

# Restart backend service
sudo systemctl restart faithtracker-backend

# Check status
sudo systemctl status faithtracker-backend

# View logs (last 50 lines)
sudo journalctl -u faithtracker-backend -n 50

# Or watch live logs
sudo journalctl -u faithtracker-backend -f
```

---

### Step 3: Update Frontend (If React Code Changed)

**When to update frontend:**
- Changes in `frontend/` folder
- New npm packages in package.json
- UI/UX changes

**Commands:**
```bash
cd /opt/faithtracker/frontend

# Install new packages (if package.json changed)
yarn install

# Build production bundle
yarn build

# Restart nginx to serve new build
sudo systemctl restart nginx

# Check status
sudo systemctl status nginx

# Test in browser
# Visit your site and hard refresh (Ctrl+Shift+R)
```

---

## Update Scenarios

### Scenario 1: Backend-Only Update

**Example:** Bug fix in server.py, new API endpoint

```bash
cd /opt/faithtracker
git pull origin main

cd backend
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart faithtracker-backend
```

**No need to touch frontend!**

---

### Scenario 2: Frontend-Only Update

**Example:** UI change, translation update

```bash
cd /opt/faithtracker
git pull origin main

cd frontend
yarn install
yarn build
sudo systemctl restart nginx
```

**No need to touch backend!**

---

### Scenario 3: Full Update (Both Changed)

**Example:** New feature with backend + frontend changes

```bash
cd /opt/faithtracker
git pull origin main

# Backend
cd backend
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart faithtracker-backend

# Frontend
cd ../frontend
yarn install
yarn build
sudo systemctl restart nginx
```

---

### Scenario 4: Database Migration

**Example:** New collections, indexes, or schema changes

```bash
cd /opt/faithtracker
git pull origin main

# Backend first
cd backend
source venv/bin/activate
pip install -r requirements.txt

# Run migration scripts
python create_performance_indexes.py  # If provided
python migrate_data.py  # If provided

# Restart
sudo systemctl restart faithtracker-backend
```

---

## Rollback Procedure

### If Update Breaks Something

**1. Check what broke:**
```bash
sudo journalctl -u faithtracker-backend -n 100
```

**2. Rollback to previous version:**
```bash
cd /opt/faithtracker
git log -5  # Find previous working commit
git checkout [commit-hash]  # Rollback to that commit
```

**3. Rebuild:**
```bash
# Backend
cd backend
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart faithtracker-backend

# Frontend
cd ../frontend
yarn install
yarn build
sudo systemctl restart nginx
```

**4. When issue resolved:**
```bash
git checkout main  # Go back to latest
```

---

## Automated Update Script

### Create Update Helper Script

```bash
sudo nano /opt/faithtracker/update.sh
```

**Paste this:**
```bash
#!/bin/bash

echo "🔄 Updating FaithTracker..."

cd /opt/faithtracker

# Pull latest code
echo "📥 Pulling latest code from GitHub..."
git pull origin main

# Update backend
echo "🔧 Updating backend..."
cd backend
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart faithtracker-backend

# Update frontend  
echo "🎨 Updating frontend..."
cd ../frontend
yarn install
yarn build

# Restart nginx
echo "🔄 Restarting Nginx..."
sudo systemctl restart nginx

# Show status
echo ""
echo "✅ Update complete!"
echo ""
sudo systemctl status faithtracker-backend --no-pager
echo ""
sudo systemctl status nginx --no-pager

echo ""
echo "🌐 Visit your site and hard refresh (Ctrl+Shift+R)"
```

**Make executable:**
```bash
sudo chmod +x /opt/faithtracker/update.sh
```

**Run anytime:**
```bash
sudo bash /opt/faithtracker/update.sh
```

---

## Troubleshooting Updates

### Backend Won't Start After Update

**Check logs:**
```bash
sudo journalctl -u faithtracker-backend -n 100
```

**Common issues:**
- Missing Python package: `pip install [package]`
- Syntax error: Check server.py line number in error
- Database connection: Check MongoDB is running

**Fix:**
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt  # Reinstall all packages
sudo systemctl restart faithtracker-backend
```

---

### Frontend Not Updating

**Hard rebuild:**
```bash
cd /opt/faithtracker/frontend
rm -rf build node_modules
yarn install
yarn build
sudo systemctl restart nginx
```

**Clear browser cache:**
- Press Ctrl+Shift+R (hard refresh)
- Or Ctrl+F5
- Or clear all browser cache

---

### Database Errors After Update

**If schema changed:**
```bash
# Check if migration script provided
ls /opt/faithtracker/backend/*.py | grep migrate

# Run migration
cd /opt/faithtracker/backend
source venv/bin/activate
python migrate_*.py
```

**Recreate indexes:**
```bash
cd /opt/faithtracker/backend
source venv/bin/activate
python create_performance_indexes.py
```

---

## Best Practices

### Before Updating

1. **Check changelog:** See what changed
2. **Backup database:**
   ```bash
   mongodump --db=pastoral_care_db --archive=/opt/faithtracker/backups/backup_$(date +%Y%m%d).gz --gzip
   ```
3. **Note current version:** `git log -1`

### During Update

1. **Low-traffic time:** Update at night or weekends
2. **Monitor logs:** Keep log window open
3. **Test immediately:** Login and check features

### After Update

1. **Verify services:** Both backend and nginx running
2. **Test critical flows:** Login, dashboard, search
3. **Check browser console:** No errors
4. **Monitor for 10 minutes:** Watch logs for issues

---

## Update Checklist

- [ ] Backup database
- [ ] Note current version
- [ ] `git pull origin main`
- [ ] Update backend (if needed)
- [ ] Update frontend (if needed)
- [ ] Restart services
- [ ] Hard refresh browser
- [ ] Test login
- [ ] Test main features
- [ ] Monitor logs
- [ ] ✅ Update complete!

---

## Quick Reference

**Check current version:**
```bash
cd /opt/faithtracker
git log -1
cat frontend/package.json | grep version
```

**See what will change before pulling:**
```bash
git fetch origin
git log HEAD..origin/main  # See commits you'll get
```

**Pull specific version:**
```bash
git pull origin main
git checkout v2.0.0  # Or specific tag
```

---

**Update time:** 2-5 minutes
**Downtime:** ~10 seconds (service restart)
**Difficulty:** Easy with update script

**Tip:** Use the automated `update.sh` script for hassle-free updates! 🚀
