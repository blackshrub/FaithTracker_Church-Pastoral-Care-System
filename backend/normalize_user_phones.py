#!/usr/bin/env python3
"""
Normalize all user phone numbers in the database
Converts local format (081xxx) to international format (+6281xxx)
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

def normalize_phone_number(phone: str, default_country_code: str = "+62") -> str:
    """
    Normalize phone number to international format.
    Handles Indonesian phone numbers starting with 0.
    """
    if not phone:
        return phone
    
    # Remove whitespace and common separators
    phone = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    
    # Already has + prefix
    if phone.startswith("+"):
        return phone
    
    # Starts with country code without +
    if phone.startswith("62"):
        return f"+{phone}"
    
    # Starts with 0 (local Indonesian format)
    if phone.startswith("0"):
        return f"{default_country_code}{phone[1:]}"
    
    # No recognizable prefix - assume it needs country code
    return f"{default_country_code}{phone}"

async def normalize_all_user_phones():
    """Normalize all user phone numbers in the database"""
    
    # Connect to MongoDB
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'pastoral_care_db')
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("🔍 Checking user phone numbers...")
    
    # Get all users
    users = await db.users.find({}, {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1}).to_list(None)
    
    updated_count = 0
    skipped_count = 0
    
    for user in users:
        original_phone = user.get('phone', '')
        
        if not original_phone:
            print(f"  ⚠️  {user['name']} ({user['email']}) - No phone number")
            skipped_count += 1
            continue
        
        normalized_phone = normalize_phone_number(original_phone)
        
        if original_phone != normalized_phone:
            print(f"  ✓ {user['name']}: {original_phone} → {normalized_phone}")
            
            # Update in database
            await db.users.update_one(
                {"id": user['id']},
                {"$set": {"phone": normalized_phone}}
            )
            updated_count += 1
        else:
            print(f"  - {user['name']}: {original_phone} (already normalized)")
            skipped_count += 1
    
    print(f"\n📊 Summary:")
    print(f"  Total users: {len(users)}")
    print(f"  Updated: {updated_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"\n✅ Phone normalization complete!")

if __name__ == "__main__":
    asyncio.run(normalize_all_user_phones())
