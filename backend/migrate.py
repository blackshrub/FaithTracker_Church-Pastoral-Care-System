#!/usr/bin/env python3
"""
FaithTracker Database Migration Script
Handles database schema changes and data transformations between versions
"""

import asyncio
import sys
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Callable

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Colors for beautiful output
GREEN = '\033[0;32m'
BLUE = '\033[0;34m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
CYAN = '\033[0;36m'
MAGENTA = '\033[0;35m'
BOLD = '\033[1m'
NC = '\033[0m'  # No Color


def print_header():
    """Print beautiful header"""
    print(f"\n{MAGENTA}{'='*60}{NC}")
    print(f"{CYAN}{BOLD}   🔄 FaithTracker Database Migration   {NC}")
    print(f"{MAGENTA}{'='*60}{NC}\n")


def print_step(message):
    """Print migration step"""
    print(f"{BLUE}▶{NC} {message}...", end='', flush=True)


def print_success(message=""):
    """Print success checkmark"""
    if message:
        print(f" {GREEN}✓{NC} {message}")
    else:
        print(f" {GREEN}✓{NC}")


def print_info(message):
    """Print info message"""
    print(f"{CYAN}ℹ{NC}  {message}")


def print_warning(message):
    """Print warning message"""
    print(f"{YELLOW}⚠{NC}  {message}")


def print_error(message):
    """Print error message"""
    print(f"\n{RED}✗ Error:{NC} {message}")


# ==================== MIGRATION DEFINITIONS ====================

async def migration_001_initial(db):
    """
    Initial migration - ensures all basic indexes exist
    (This is for existing deployments that didn't have init_db.py)
    """
    # Users collection
    await db.users.create_index("email", unique=True)
    await db.users.create_index("campus_id")
    await db.users.create_index("role")

    # Campuses collection
    await db.campuses.create_index("id", unique=True)

    return "Initial indexes created"


async def migration_002_add_activity_logs_indexes(db):
    """Add indexes for activity logs collection"""
    await db.activity_logs.create_index("campus_id")
    await db.activity_logs.create_index("action_date")
    await db.activity_logs.create_index("user_id")
    return "Activity logs indexes created"


async def migration_003_add_api_sync_collections(db):
    """Add indexes for API sync functionality"""
    # API sync configs
    await db.api_sync_configs.create_index("campus_id", unique=True)

    # API sync history
    await db.api_sync_history.create_index("campus_id")
    await db.api_sync_history.create_index("sync_started_at")
    await db.api_sync_history.create_index("status")

    return "API sync indexes created"


async def migration_004_normalize_phone_numbers(db):
    """Normalize phone numbers to international format (62xxx)"""
    members_updated = 0

    cursor = db.members.find({"phone": {"$exists": True, "$ne": ""}})
    async for member in cursor:
        phone = member.get("phone", "").strip()
        if phone:
            # Normalize phone format
            if phone.startswith("0"):
                normalized = "62" + phone[1:]
            elif phone.startswith("+62"):
                normalized = phone[1:]
            elif phone.startswith("62"):
                normalized = phone
            else:
                continue  # Skip invalid formats

            if normalized != phone:
                await db.members.update_one(
                    {"_id": member["_id"]},
                    {"$set": {"phone": normalized}}
                )
                members_updated += 1

    return f"Normalized {members_updated} phone numbers"


async def migration_005_add_deleted_fields(db):
    """Add soft delete fields to all documents that don't have them"""
    collections = ["members", "care_events", "campuses", "users"]
    total_updated = 0

    for collection_name in collections:
        collection = db[collection_name]
        result = await collection.update_many(
            {"deleted": {"$exists": False}},
            {"$set": {"deleted": False, "deleted_at": None}}
        )
        total_updated += result.modified_count

    return f"Added soft delete fields to {total_updated} documents"


async def migration_006_ensure_campus_is_active(db):
    """Ensure all campuses have is_active field (required for login selection)"""
    result = await db.campuses.update_many(
        {"is_active": {"$exists": False}},
        {"$set": {"is_active": True}}
    )
    return f"Set is_active=True on {result.modified_count} campus(es)"


async def migration_007_fix_user_password_field(db):
    """Rename password_hash to hashed_password for consistency with server.py"""
    # Find users with old field name
    result = await db.users.update_many(
        {"password_hash": {"$exists": True}, "hashed_password": {"$exists": False}},
        [{"$set": {"hashed_password": "$password_hash"}}, {"$unset": "password_hash"}]
    )

    # Also ensure is_active exists
    await db.users.update_many(
        {"is_active": {"$exists": False}},
        {"$set": {"is_active": True}}
    )

    return f"Fixed password field on {result.modified_count} user(s)"


async def migration_008_ensure_campus_id_field(db):
    """Ensure all campuses have an 'id' field (required for frontend selection)"""
    import uuid

    campuses_updated = 0
    cursor = db.campuses.find({"id": {"$exists": False}})

    async for campus in cursor:
        # Generate a UUID for the campus id field
        new_id = str(uuid.uuid4())
        await db.campuses.update_one(
            {"_id": campus["_id"]},
            {"$set": {"id": new_id}}
        )
        campuses_updated += 1

    return f"Added id field to {campuses_updated} campus(es)"


async def migration_009_ensure_user_required_fields(db):
    """Ensure all users have required fields for login (id, phone, created_at, name)"""
    import uuid

    users_fixed = 0
    now = datetime.now(timezone.utc).isoformat()

    # Find all users and ensure they have all required fields
    cursor = db.users.find({})
    async for user in cursor:
        updates = {}

        # Add 'id' if missing
        if "id" not in user:
            updates["id"] = str(uuid.uuid4())

        # Add 'phone' if missing (can be empty string)
        if "phone" not in user:
            updates["phone"] = ""

        # Add 'name' if missing
        if "name" not in user:
            updates["name"] = user.get("email", "Unknown User").split("@")[0]

        # Add 'created_at' if missing
        if "created_at" not in user:
            updates["created_at"] = now

        # Add 'updated_at' if missing
        if "updated_at" not in user:
            updates["updated_at"] = now

        # Add 'is_active' if missing
        if "is_active" not in user:
            updates["is_active"] = True

        # Apply updates if any
        if updates:
            await db.users.update_one(
                {"_id": user["_id"]},
                {"$set": updates}
            )
            users_fixed += 1

    return f"Fixed {users_fixed} user(s) with missing required fields"


# ==================== MIGRATION REGISTRY ====================

# List of all migrations in order
# Format: (version_number, description, migration_function)
MIGRATIONS: List[tuple[int, str, Callable]] = [
    (1, "Initial indexes", migration_001_initial),
    (2, "Activity logs indexes", migration_002_add_activity_logs_indexes),
    (3, "API sync collections", migration_003_add_api_sync_collections),
    (4, "Normalize phone numbers", migration_004_normalize_phone_numbers),
    (5, "Add soft delete fields", migration_005_add_deleted_fields),
    (6, "Ensure campus is_active field", migration_006_ensure_campus_is_active),
    (7, "Fix user password field name", migration_007_fix_user_password_field),
    (8, "Ensure campus id field", migration_008_ensure_campus_id_field),
    (9, "Ensure user required fields", migration_009_ensure_user_required_fields),
]


# ==================== MIGRATION ENGINE ====================

async def get_current_version(db) -> int:
    """Get the current database version from migrations collection"""
    migration_doc = await db.migrations.find_one({"_id": "version"})
    if migration_doc:
        return migration_doc.get("version", 0)
    return 0


async def set_current_version(db, version: int):
    """Update the current database version"""
    await db.migrations.update_one(
        {"_id": "version"},
        {"$set": {
            "version": version,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )


async def log_migration(db, version: int, description: str, success: bool, message: str):
    """Log migration execution to history"""
    await db.migrations_history.insert_one({
        "version": version,
        "description": description,
        "success": success,
        "message": message,
        "executed_at": datetime.now(timezone.utc).isoformat()
    })


async def run_migrations(db, current_version: int):
    """Run all pending migrations"""
    pending_migrations = [m for m in MIGRATIONS if m[0] > current_version]

    if not pending_migrations:
        print_info("No pending migrations")
        return True

    print(f"\n{CYAN}Found {len(pending_migrations)} pending migration(s):{NC}\n")

    for version, description, migration_func in pending_migrations:
        print_step(f"v{version:03d}: {description}")

        try:
            result = await migration_func(db)
            await log_migration(db, version, description, True, result)
            await set_current_version(db, version)
            print_success(result)

        except Exception as e:
            error_msg = f"Migration failed: {str(e)}"
            print_error(error_msg)
            await log_migration(db, version, description, False, error_msg)
            return False

    return True


async def show_migration_history(db):
    """Display migration history"""
    print(f"\n{CYAN}Migration History:{NC}\n")

    cursor = db.migrations_history.find().sort("executed_at", -1).limit(10)
    history = await cursor.to_list(10)

    if not history:
        print_info("No migration history found")
        return

    for record in history:
        status_icon = f"{GREEN}✓{NC}" if record.get("success") else f"{RED}✗{NC}"
        version = record.get("version", 0)
        desc = record.get("description", "")
        executed = record.get("executed_at", "")[:19]  # Trim to datetime
        print(f"  {status_icon} v{version:03d} - {desc} ({executed})")


async def run_migration_process():
    """Main migration process"""
    print_header()

    # Get configuration
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME', 'pastoral_care_db')

    if not mongo_url:
        print_error("MONGO_URL not set in environment")
        return False

    try:
        # Connect to database
        print_step("Connecting to database")
        client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
        await client.admin.command('ping')
        db = client[db_name]
        print_success(f"Connected to {db_name}")

        # Get current version
        current_version = await get_current_version(db)
        latest_version = max([m[0] for m in MIGRATIONS]) if MIGRATIONS else 0

        print_info(f"Current database version: v{current_version:03d}")
        print_info(f"Latest available version: v{latest_version:03d}")

        if current_version >= latest_version:
            print(f"\n{GREEN}{'='*60}{NC}")
            print(f"{GREEN}{BOLD}   ✓ Database is up to date!   {NC}")
            print(f"{GREEN}{'='*60}{NC}\n")
        else:
            # Run migrations
            success = await run_migrations(db, current_version)

            if success:
                print(f"\n{GREEN}{'='*60}{NC}")
                print(f"{GREEN}{BOLD}   ✓ All migrations completed successfully!   {NC}")
                print(f"{GREEN}{'='*60}{NC}\n")

                new_version = await get_current_version(db)
                print(f"{CYAN}📊 Summary:{NC}")
                print(f"   Previous version:  v{current_version:03d}")
                print(f"   Current version:   v{new_version:03d}")
                print(f"   Migrations run:    {new_version - current_version}")
            else:
                print(f"\n{RED}{'='*60}{NC}")
                print(f"{RED}{BOLD}   ✗ Migration failed!   {NC}")
                print(f"{RED}{'='*60}{NC}\n")
                print_warning("Database may be in an inconsistent state")
                print_warning("Review the error above and fix before retrying")

        # Show migration history
        await show_migration_history(db)

        client.close()
        return success if current_version < latest_version else True

    except Exception as e:
        print_error(str(e))
        return False


def main():
    """Main entry point"""
    success = asyncio.run(run_migration_process())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
