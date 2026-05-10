import asyncio
import csv
import os

from pymongo import AsyncMongoClient


async def import_member_photos():
    """Import member photos based on CSV photo column"""

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    client = AsyncMongoClient(mongo_url)
    db = client[os.environ.get("DB_NAME", "pastoral_care_db")]

    print("Importing member photos...")

    updated_count = 0
    not_found_count = 0

    with open("/app/backend/core_jemaat.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                identity_jemaat = row.get("identity_jemaat", "").strip()
                photo_filename = row.get("photo", "").strip()

                if not identity_jemaat or not photo_filename:
                    continue

                # Find member by external_member_id
                member = await db.members.find_one({"external_member_id": identity_jemaat}, {"_id": 0})

                if member:
                    # Check if photo file exists
                    photo_path = f"/app/backend/uploads/{photo_filename}"
                    if os.path.exists(photo_path):
                        # Update member with photo URL
                        await db.members.update_one(
                            {"id": member["id"]}, {"$set": {"photo_url": f"/uploads/{photo_filename}"}}
                        )
                        updated_count += 1

                        if updated_count % 50 == 0:
                            print(f"  Updated {updated_count} photos...")
                    else:
                        not_found_count += 1

            except Exception as e:
                print(f"Error processing {row.get('identity_jemaat')}: {e!s}")

    print("\n✅ Photo import complete!")
    print(f"  Updated: {updated_count} members")
    print(f"  Not found: {not_found_count} photos")

    client.close()


if __name__ == "__main__":
    asyncio.run(import_member_photos())
