#!/usr/bin/env bash
# FaithTracker — Daily WhatsApp Digest Heartbeat
#
# Why: a 2026-04-29 startup race left the in-process APScheduler unregistered
# for 10 days, silently dropping the 06:00 WIB digest. This is the dead-man's
# switch that alerts the admin via WhatsApp + email when no digest was sent
# today, regardless of which internal layer failed.
#
# Schedule: every day at 07:00 Asia/Jakarta (1 hour after digest).
# Exit codes: 0 healthy, 1 alert fired, 2 setup error.
set -euo pipefail

PROJECT_ROOT="/srv/FaithTracker_Church-Pastoral-Care-System"
LOG_DIR="$PROJECT_ROOT/data/logs"
LOG_FILE="$LOG_DIR/digest-heartbeat.log"
ENV_FILE="$PROJECT_ROOT/.env"
MONGO_PWD_FILE="$PROJECT_ROOT/secrets/mongo_password"

mkdir -p "$LOG_DIR"
exec >> "$LOG_FILE" 2>&1

ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }
echo "[$(ts)] heartbeat: start"

if [ ! -f "$MONGO_PWD_FILE" ]; then
  echo "[$(ts)] heartbeat: ERROR mongo password file missing at $MONGO_PWD_FILE"
  exit 2
fi
MONGO_PWD="$(cat "$MONGO_PWD_FILE")"

# Count today's pastoral digest notifications (Jakarta day boundary).
# We only trust 'sent' rows with pastoral_team_user_id — the field daily_reminder_job sets.
COUNT="$(docker exec faithtracker-mongo mongosh --quiet \
  -u admin -p "$MONGO_PWD" --authenticationDatabase admin \
  --eval '
const db = db.getSiblingDB("faithtracker");
const jakartaToday = new Date(new Date().toLocaleString("en-US", {timeZone: "Asia/Jakarta"}));
const todayStart = new Date(jakartaToday.getFullYear(), jakartaToday.getMonth(), jakartaToday.getDate(), 0, 0, 0);
// Convert local-Jakarta midnight back to UTC for the query (Jakarta = UTC+7).
const todayStartUtc = new Date(todayStart.getTime() - 7*60*60*1000);
print(db.notification_logs.countDocuments({
  pastoral_team_user_id: {$exists: true},
  status: "sent",
  created_at: {$gte: todayStartUtc}
}));
' 2>/dev/null | tr -d '[:space:]')"

if ! [[ "$COUNT" =~ ^[0-9]+$ ]]; then
  echo "[$(ts)] heartbeat: ERROR mongo query returned non-numeric: '$COUNT'"
  COUNT=0  # Fall through to alert path — assume worst-case and notify
fi

if [ "$COUNT" -gt 0 ]; then
  echo "[$(ts)] heartbeat: OK $COUNT digest message(s) sent today"
  exit 0
fi

echo "[$(ts)] heartbeat: ALERT no digest sent today — firing notifications"

# Pull alert destinations from .env
get_env() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'; }
ADMIN_PHONE="$(get_env ADMIN_PHONE)"
WA_GATEWAY="$(get_env WHATSAPP_GATEWAY_URL)"
ALERT_EMAIL="$(get_env ALERT_EMAIL)"

ALERT_DATE="$(TZ='Asia/Jakarta' date '+%Y-%m-%d %H:%M %Z')"
ALERT_BODY="🚨 *FaithTracker Heartbeat*

Tidak ada WhatsApp digest pastoral yang terkirim hari ini ($ALERT_DATE).

Periksa:
1. docker logs faithtracker-backend --since 24h | grep -iE 'digest|scheduler'
2. curl http://localhost:8001/health/scheduler
3. Status WhatsApp gateway: ${WA_GATEWAY:-(not set)}/health"

# WhatsApp self-alert (won't help if gateway itself is the failure, but worth trying)
if [ -n "$WA_GATEWAY" ] && [ -n "$ADMIN_PHONE" ]; then
  if curl -fsS --max-time 15 -X POST "$WA_GATEWAY/send/message" \
       -H 'Content-Type: application/json' \
       -d "$(printf '{"phone":"%s@s.whatsapp.net","message":%s}' \
              "$ADMIN_PHONE" "$(printf '%s' "$ALERT_BODY" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))')")" \
       > /dev/null; then
    echo "[$(ts)] heartbeat: WhatsApp alert sent to $ADMIN_PHONE"
  else
    echo "[$(ts)] heartbeat: WhatsApp alert FAILED (gateway may also be down)"
  fi
fi

# Email alert via the backend container (reuses SMTP env + smtplib already in image)
if [ -n "$ALERT_EMAIL" ]; then
  if docker exec -i faithtracker-backend python -c "
import asyncio, sys
sys.path.insert(0, '/app')
from scheduler import send_email_alert
asyncio.run(send_email_alert(
    subject='[FaithTracker] CRITICAL: Daily digest not sent today',
    body='''$(printf '%s' "$ALERT_BODY" | sed "s/'/\\\\'/g")
'''
))
" 2>&1; then
    echo "[$(ts)] heartbeat: email alert sent to $ALERT_EMAIL"
  else
    echo "[$(ts)] heartbeat: email alert FAILED"
  fi
else
  echo "[$(ts)] heartbeat: ALERT_EMAIL not set, skipping email"
fi

exit 1
