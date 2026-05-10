#!/usr/bin/env python3
"""
Bulk Engagement Status Update
Uses MongoDB aggregation pipeline for 10-100x faster updates compared to individual calculations

This script updates engagement_status and days_since_last_contact for all members
in a single aggregation operation using MongoDB's powerful aggregation framework.

Performance:
- Old method: Calculate per member (1000 members = 1000 queries)
- New method: Single aggregation pipeline (1000 members = 1 query)
- Speed improvement: 10-100x faster depending on dataset size

Usage:
    python bulk_engagement_update.py [--campus-id CAMPUS_ID] [--dry-run]
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# Jakarta timezone (UTC+7)
JAKARTA_TZ = ZoneInfo("Asia/Jakarta")

# Colors for output
GREEN = "\033[0;32m"
BLUE = "\033[0;34m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
NC = "\033[0m"  # No Color


def now_jakarta():
    """Get current time in Jakarta timezone"""
    return datetime.now(JAKARTA_TZ)


async def bulk_update_engagement_statuses(db, campus_id=None, dry_run=False):
    """
    Update engagement statuses for all members using MongoDB aggregation pipeline

    Args:
        db: MongoDB database instance
        campus_id: Optional campus ID to filter (None = all campuses)
        dry_run: If True, only show what would be updated without making changes

    Returns:
        dict: Statistics about the update
    """

    print(f"{CYAN}{BOLD}🔄 Bulk Engagement Status Update{NC}\n")

    # Build match stage
    match_stage = {"deleted": {"$ne": True}, "is_archived": {"$ne": True}}
    if campus_id:
        match_stage["campus_id"] = campus_id
        print(f"{BLUE}📍 Campus filter:{NC} {campus_id}")
    else:
        print(f"{BLUE}📍 Scope:{NC} All campuses")

    print(f"{BLUE}🏃 Mode:{NC} {'DRY RUN (no changes)' if dry_run else 'LIVE UPDATE'}")
    print()

    # Get current count before update
    total_members = await db.members.count_documents(match_stage)
    print(f"{CYAN}Total members to process:{NC} {total_members:,}")

    if total_members == 0:
        print(f"{YELLOW}⚠ No members found to update{NC}")
        return {"total": 0, "updated": 0}

    # Calculate current date in Jakarta timezone
    now = now_jakarta()
    current_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if dry_run:
        # In dry-run mode, just count what would be updated
        print(f"\n{YELLOW}📊 Analyzing engagement status distribution...{NC}\n")

        pipeline = [
            {"$match": match_stage},
            {
                "$addFields": {
                    "days_since_contact": {
                        "$cond": [
                            {"$ne": ["$last_contact_date", None]},
                            {
                                "$divide": [
                                    {
                                        "$subtract": [
                                            current_date,
                                            {
                                                "$dateFromString": {
                                                    "dateString": "$last_contact_date",
                                                    # Force Asia/Jakarta interpretation. Without an
                                                    # explicit timezone, $dateFromString uses the
                                                    # offset embedded in the string (when present),
                                                    # producing a 7-hour drift versus current_date
                                                    # for any record that happens to carry a
                                                    # +HH:MM suffix. Misclassifies engagement.
                                                    "timezone": "Asia/Jakarta",
                                                    "onError": None,
                                                }
                                            },
                                        ]
                                    },
                                    86400000,  # milliseconds in a day
                                ]
                            },
                            999,
                        ]
                    }
                }
            },
            {
                "$addFields": {
                    "new_engagement_status": {
                        "$switch": {
                            "branches": [
                                {"case": {"$lte": ["$days_since_contact", 60]}, "then": "active"},
                                {"case": {"$lte": ["$days_since_contact", 180]}, "then": "at_risk"},
                            ],
                            "default": "disconnected",
                        }
                    }
                }
            },
            {"$group": {"_id": "$new_engagement_status", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]

        result = await db.members.aggregate(pipeline).to_list(None)

        for status_group in result:
            status = status_group["_id"]
            count = status_group["count"]
            percentage = (count / total_members) * 100

            # Color code by status
            if status == "active":
                color = GREEN
            elif status == "at_risk":
                color = YELLOW
            else:
                color = BLUE

            print(f"  {color}●{NC} {status.upper():15} {count:6,} members ({percentage:5.1f}%)")

        print(f"\n{GREEN}✓ Dry run complete{NC}")
        print(f"{CYAN}💡 Run without --dry-run to apply changes{NC}\n")

        return {
            "total": total_members,
            "updated": 0,
            "dry_run": True,
            "distribution": {r["_id"]: r["count"] for r in result},
        }

    else:
        # Live update using aggregation pipeline with $merge
        print(f"\n{CYAN}⚡ Running bulk update...{NC}")

        pipeline = [
            {"$match": match_stage},
            {
                "$addFields": {
                    # Calculate days since last contact
                    "days_since_contact_calc": {
                        "$cond": [
                            {"$ne": ["$last_contact_date", None]},
                            {
                                "$toInt": {
                                    "$divide": [
                                        {
                                            "$subtract": [
                                                current_date,
                                                {
                                                    "$dateFromString": {
                                                        "dateString": "$last_contact_date",
                                                        # See above — explicit Jakarta timezone
                                                        # avoids 7-hour misclassification.
                                                        "timezone": "Asia/Jakarta",
                                                        "onError": None,
                                                        "onNull": None,
                                                    }
                                                },
                                            ]
                                        },
                                        86400000,  # milliseconds in a day
                                    ]
                                }
                            },
                            999,
                        ]
                    }
                }
            },
            {
                "$addFields": {
                    # Calculate new engagement status based on days
                    "engagement_status": {
                        "$switch": {
                            "branches": [
                                {"case": {"$lte": ["$days_since_contact_calc", 60]}, "then": "active"},
                                {"case": {"$lte": ["$days_since_contact_calc", 180]}, "then": "at_risk"},
                            ],
                            "default": "disconnected",
                        }
                    },
                    # Update days_since_last_contact field
                    "days_since_last_contact": "$days_since_contact_calc",
                    # Update timestamp
                    "updated_at": now.isoformat(),
                }
            },
            {
                "$project": {
                    "days_since_contact_calc": 0  # Remove temporary field
                }
            },
            {
                # Merge back to members collection
                "$merge": {"into": "members", "whenMatched": "merge", "whenNotMatched": "discard"}
            },
        ]

        # Execute the aggregation pipeline
        start_time = datetime.now()

        try:
            await db.members.aggregate(pipeline).to_list(None)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            print(f"{GREEN}✓ Update complete!{NC}\n")
            print(f"{CYAN}📊 Statistics:{NC}")
            print(f"  • Members processed: {BOLD}{total_members:,}{NC}")
            print(f"  • Time taken: {BOLD}{duration:.2f}s{NC}")
            print(f"  • Speed: {BOLD}{int(total_members / duration):,} members/second{NC}")

            # Show updated distribution
            print(f"\n{CYAN}📈 Updated Distribution:{NC}")

            status_counts = await db.members.aggregate(
                [
                    {"$match": match_stage},
                    {"$group": {"_id": "$engagement_status", "count": {"$sum": 1}}},
                    {"$sort": {"_id": 1}},
                ]
            ).to_list(None)

            for status_group in status_counts:
                status = status_group["_id"]
                count = status_group["count"]
                percentage = (count / total_members) * 100

                if status == "active":
                    color = GREEN
                elif status == "at_risk":
                    color = YELLOW
                else:
                    color = BLUE

                print(f"  {color}●{NC} {status.upper():15} {count:6,} members ({percentage:5.1f}%)")

            print()

            return {
                "total": total_members,
                "updated": total_members,
                "duration": duration,
                "speed": int(total_members / duration),
                "distribution": {r["_id"]: r["count"] for r in status_counts},
            }

        except Exception as e:
            print(f"{YELLOW}⚠ Error during update:{NC} {e!s}")
            raise


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Bulk update member engagement statuses using MongoDB aggregation")
    parser.add_argument(
        "--campus-id", help="Update only members from specific campus (default: all campuses)", default=None
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without making changes")

    args = parser.parse_args()

    # Get database connection
    mongo_url = os.getenv("MONGO_URL")
    db_name = os.getenv("DB_NAME", "pastoral_care_db")

    if not mongo_url:
        print(f"{YELLOW}⚠ MONGO_URL not set in environment{NC}")
        sys.exit(1)

    try:
        # Connect to database
        client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
        await client.admin.command("ping")
        db = client[db_name]

        # Run bulk update
        await bulk_update_engagement_statuses(db, campus_id=args.campus_id, dry_run=args.dry_run)

        client.close()

        sys.exit(0)

    except Exception as e:
        print(f"{YELLOW}⚠ Error:{NC} {e!s}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
