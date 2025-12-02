#!/usr/bin/env python3
"""
Fix corrupted care event IDs in the database.
This script regenerates valid UUID strings for all care events with corrupted IDs.
"""

import asyncio
import uuid
import re
import os
from motor.motor_asyncio import AsyncIOMotorClient

# Valid UUID pattern
UUID_PATTERN = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')

def is_valid_uuid(value):
    """Check if a string is a valid UUID format."""
    if not isinstance(value, str):
        return False
    return bool(UUID_PATTERN.match(value))

async def fix_care_event_ids():
    """Fix all care events with corrupted IDs."""
    # Connect to MongoDB - use 'mongo' hostname for container networking
    mongo_uri = os.environ.get("MONGODB_URI", "mongodb://admin:fefb33c5e0eee893f2ee752a480cacc6@mongo:27017/faithtracker?authSource=admin")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.faithtracker

    print("Checking care events for corrupted IDs...")

    # Get all care events
    events = await db.care_events.find({}).to_list(None)
    total = len(events)
    corrupted_count = 0
    fixed_count = 0

    print(f"Total care events: {total}")

    for event in events:
        event_id = event.get("id")
        mongo_id = event.get("_id")

        if not is_valid_uuid(event_id):
            corrupted_count += 1
            # Generate new valid UUID
            new_id = str(uuid.uuid4())

            # Update the event with new ID
            result = await db.care_events.update_one(
                {"_id": mongo_id},
                {"$set": {"id": new_id}}
            )

            if result.modified_count > 0:
                fixed_count += 1
                if fixed_count <= 10:  # Print first 10 fixes
                    print(f"  Fixed event {mongo_id}: '{event_id[:20] if event_id else 'None'}...' -> '{new_id}'")

    print(f"\nResults:")
    print(f"  Total events: {total}")
    print(f"  Corrupted IDs found: {corrupted_count}")
    print(f"  IDs fixed: {fixed_count}")

    # Verify fix
    print("\nVerifying fix...")
    remaining = 0
    async for event in db.care_events.find({}):
        if not is_valid_uuid(event.get("id")):
            remaining += 1

    print(f"  Remaining corrupted IDs: {remaining}")

    if remaining == 0:
        print("\n✅ All care event IDs are now valid UUIDs!")
    else:
        print(f"\n⚠️ Warning: {remaining} events still have invalid IDs")

    client.close()

if __name__ == "__main__":
    asyncio.run(fix_care_event_ids())
