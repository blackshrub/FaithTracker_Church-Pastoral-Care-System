#!/usr/bin/env python3
"""
FaithTracker Database Initialization Script
Initializes database for fresh installations with indexes, admin user, and essential data
"""

import asyncio
import argparse
import sys
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Colors for beautiful output
GREEN = '\033[0;32m'
BLUE = '\033[0;34m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
CYAN = '\033[0;36m'
BOLD = '\033[1m'
NC = '\033[0m'  # No Color


def print_header():
    """Print beautiful header"""
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{CYAN}{BOLD}   🚀 FaithTracker Database Initialization   {NC}")
    print(f"{BLUE}{'='*60}{NC}\n")


def print_step(step_num, total_steps, message):
    """Print step progress"""
    print(f"{BLUE}[{step_num}/{total_steps}]{NC} {message}...", end='', flush=True)


def print_success(message=""):
    """Print success checkmark"""
    if message:
        print(f" {GREEN}✓{NC} {message}")
    else:
        print(f" {GREEN}✓{NC}")


def print_error(message):
    """Print error message"""
    print(f"\n{RED}✗ Error:{NC} {message}")


async def test_connection(mongo_url, db_name):
    """Test MongoDB connection"""
    try:
        client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
        await client.admin.command('ping')
        return client
    except Exception as e:
        raise Exception(f"Cannot connect to MongoDB: {str(e)}")


async def create_indexes(db):
    """Create all database indexes"""
    indexes_created = 0

    # Members collection indexes
    await db.members.create_index("campus_id")
    await db.members.create_index("family_group_id")
    await db.members.create_index("last_contact_date")
    await db.members.create_index("engagement_status")
    await db.members.create_index("external_member_id")
    await db.members.create_index([("name", "text"), ("phone", "text")])
    indexes_created += 6

    # Care events collection indexes
    await db.care_events.create_index("member_id")
    await db.care_events.create_index("campus_id")
    await db.care_events.create_index("event_date")
    await db.care_events.create_index("event_type")
    await db.care_events.create_index("completed")
    await db.care_events.create_index([("member_id", 1), ("event_date", -1)])
    indexes_created += 6

    # Grief support collection indexes
    await db.grief_support.create_index("member_id")
    await db.grief_support.create_index("campus_id")
    await db.grief_support.create_index("scheduled_date")
    await db.grief_support.create_index("completed")
    await db.grief_support.create_index("care_event_id")
    indexes_created += 5

    # Financial aid schedules indexes
    await db.financial_aid_schedules.create_index("member_id")
    await db.financial_aid_schedules.create_index("campus_id")
    await db.financial_aid_schedules.create_index("next_occurrence")
    await db.financial_aid_schedules.create_index("is_active")
    await db.financial_aid_schedules.create_index("frequency")
    indexes_created += 5

    # Notification logs indexes
    await db.notification_logs.create_index("created_at")
    await db.notification_logs.create_index("member_id")
    await db.notification_logs.create_index("status")
    indexes_created += 3

    # Users collection indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("campus_id")
    await db.users.create_index("role")
    indexes_created += 3

    # Family groups indexes
    await db.family_groups.create_index("campus_id")
    indexes_created += 1

    # Campuses indexes
    await db.campuses.create_index("id", unique=True)
    indexes_created += 1

    # Activity logs indexes
    await db.activity_logs.create_index("campus_id")
    await db.activity_logs.create_index("action_date")
    await db.activity_logs.create_index("user_id")
    indexes_created += 3

    return indexes_created


async def create_admin_user(db, email, password, name="Administrator"):
    """Create admin user if doesn't exist"""
    existing = await db.users.find_one({"email": email})
    if existing:
        return False, "Admin user already exists"

    user = {
        "email": email,
        "password_hash": pwd_context.hash(password),
        "name": name,
        "role": "full_admin",
        "campus_id": None,  # Full admin has no specific campus
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    await db.users.insert_one(user)
    return True, "Admin user created successfully"


async def create_default_campus(db, church_name):
    """Create default campus if none exist"""
    existing = await db.campuses.find_one({})
    if existing:
        return False, "Campus already exists"

    import uuid
    campus = {
        "id": str(uuid.uuid4()),
        "campus_name": f"{church_name} - Main Campus",
        "address": "",
        "city": "",
        "phone": "",
        "head_pastor": "",
        "is_active": True,  # Required for campus to show in login selection
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    await db.campuses.insert_one(campus)
    return True, f"Default campus created: {campus['campus_name']}"


async def initialize_database(args):
    """Main initialization function"""
    print_header()

    # Get configuration
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME', 'pastoral_care_db')

    if not mongo_url:
        print_error("MONGO_URL not set in environment")
        return False

    total_steps = 5
    current_step = 0

    try:
        # Step 1: Test connection
        current_step += 1
        print_step(current_step, total_steps, "Testing database connection")
        client = await test_connection(mongo_url, db_name)
        db = client[db_name]
        print_success(f"Connected to {db_name}")

        # Step 2: Create indexes
        current_step += 1
        print_step(current_step, total_steps, "Creating database indexes")
        indexes_count = await create_indexes(db)
        print_success(f"{indexes_count} indexes created")

        # Step 3: Create admin user
        current_step += 1
        print_step(current_step, total_steps, "Creating admin user")
        created, message = await create_admin_user(
            db,
            args.admin_email,
            args.admin_password,
            args.admin_name
        )
        if created:
            print_success(f"{args.admin_email}")
        else:
            print_success(message)

        # Step 4: Create default campus
        current_step += 1
        print_step(current_step, total_steps, "Creating default campus")
        created, message = await create_default_campus(db, args.church_name)
        print_success(message if created else "Using existing campus")

        # Step 5: Verify setup
        current_step += 1
        print_step(current_step, total_steps, "Verifying database setup")

        # Count collections
        users_count = await db.users.count_documents({})
        campuses_count = await db.campuses.count_documents({})

        print_success(f"{users_count} user(s), {campuses_count} campus(es)")

        # Print summary
        print(f"\n{GREEN}{'='*60}{NC}")
        print(f"{GREEN}{BOLD}   ✓ Database initialized successfully!   {NC}")
        print(f"{GREEN}{'='*60}{NC}\n")

        print(f"{CYAN}📊 Summary:{NC}")
        print(f"   Database:  {BOLD}{db_name}{NC}")
        print(f"   Admin:     {BOLD}{args.admin_email}{NC}")
        print(f"   Church:    {BOLD}{args.church_name}{NC}")
        print(f"   Indexes:   {BOLD}{indexes_count}{NC}")
        print()

        client.close()
        return True

    except Exception as e:
        print_error(str(e))
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Initialize FaithTracker database for fresh installation'
    )
    parser.add_argument('--admin-email', required=True, help='Admin user email')
    parser.add_argument('--admin-password', required=True, help='Admin user password')
    parser.add_argument('--admin-name', default='Administrator', help='Admin user name')
    parser.add_argument('--church-name', default='GKBJ', help='Church name')

    args = parser.parse_args()

    # Validate email
    if '@' not in args.admin_email:
        print_error("Invalid email format")
        sys.exit(1)

    # Validate password
    if len(args.admin_password) < 8:
        print_error("Password must be at least 8 characters")
        sys.exit(1)

    # Run initialization
    success = asyncio.run(initialize_database(args))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
