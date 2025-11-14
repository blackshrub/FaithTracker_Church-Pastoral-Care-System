#!/usr/bin/env python3
"""
Recalculate engagement status for all members
Run after fixing engagement status thresholds
"""
import asyncio
from pymongo import MongoClient
from datetime import datetime, timezone

def calculate_engagement_status(last_contact):
    """Calculate engagement status"""
    if not last_contact:
        return "inactive", 999
    
    # Handle string dates
    if isinstance(last_contact, str):
        try:
            last_contact = datetime.fromisoformat(last_contact)
        except:
            return "inactive", 999
    
    # Make timezone-aware if needed
    if last_contact.tzinfo is None:
        last_contact = last_contact.replace(tzinfo=timezone.utc)
    
    now = datetime.now(timezone.utc)
    days_since = (now - last_contact).days
    
    if days_since < 30:
        return "active", days_since
    elif days_since < 60:
        return "at_risk", days_since
    elif days_since < 90:
        return "inactive", days_since
    else:
        return "disconnected", days_since

async def main():
    client = MongoClient('mongodb://localhost:27017')
    db = client['pastoral_care_db']
    
    members = list(db.members.find({}, {"_id": 0, "id": 1, "name": 1, "last_contact_date": 1}))
    
    print(f"Recalculating engagement status for {len(members)} members...")
    
    updated = 0
    for member in members:
        status, days = calculate_engagement_status(member.get("last_contact_date"))
        
        db.members.update_one(
            {"id": member["id"]},
            {"$set": {
                "engagement_status": status,
                "days_since_last_contact": days,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        updated += 1
    
    print(f"\n✅ Updated {updated} members")
    
    # Show stats
    stats = {}
    for member in db.members.find({}, {"_id": 0, "engagement_status": 1}):
        status = member.get("engagement_status", "unknown")
        stats[status] = stats.get(status, 0) + 1
    
    print("\nEngagement Status Distribution:")
    for status, count in sorted(stats.items()):
        print(f"  {status}: {count}")

if __name__ == "__main__":
    asyncio.run(main())
