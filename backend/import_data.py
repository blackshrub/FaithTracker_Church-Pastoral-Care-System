import asyncio
import csv
import random
from datetime import datetime, date, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os
import uuid
from collections import defaultdict

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'pastoral_care_db')]

async def import_campuses_and_data():
    """Import campuses, members, and generate realistic pastoral care data"""
    
    print("="*60)
    print("GKBJ DATA IMPORT & DUMMY DATA GENERATION")
    print("="*60)
    
    # Step 1: Extract and create campuses
    print("\n1. Extracting campuses from CSV...")
    campuses_map = {}
    campus_names_found = set()
    
    with open('/app/backend/core_jemaat.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            baptist_place = row.get('baptist_place', '').strip()
            if baptist_place and baptist_place not in campus_names_found:
                campus_names_found.add(baptist_place)
    
    # Create campuses
    for campus_name in sorted(campus_names_found):
        if campus_name:  # Skip empty
            campus_id = str(uuid.uuid4())
            campus_obj = {
                "id": campus_id,
                "campus_name": campus_name,
                "location": None,
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            await db.campuses.insert_one(campus_obj)
            campuses_map[campus_name] = campus_id
            print(f"  ✓ Created campus: {campus_name}")
    
    print(f"\n✅ Created {len(campuses_map)} campuses")
    
    # Step 2: Import members with family grouping
    print("\n2. Importing 696 members with family grouping...")
    
    family_groups_map = {}  # kk_name -> {campus_id -> family_group_id}
    members_imported = 0
    members_skipped = 0
    
    with open('/app/backend/core_jemaat.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                name = row.get('name_full', '').strip()
                phone = row.get('number_hp', '').strip()
                
                if not name or not phone:
                    members_skipped += 1
                    continue
                
                # Format phone number properly
                if phone.startswith('0'):
                    phone = '62' + phone[1:]
                elif phone.startswith('+'):
                    phone = phone[1:]
                # If no phone, set to empty (children, etc.)
                if not phone or phone == '62':
                    phone = ''
                
                # Parse membership status
                membership_map = {
                    '1': 'Member',
                    '2': 'Non Member', 
                    '7': 'Visitor',
                    '8': 'Sympathizer',
                    '9': 'Member (Inactive)'
                }
                membership_status = membership_map.get(row.get('membership_id', ''), 'Unknown')
                
                # Get campus
                baptist_place = row.get('baptist_place', '').strip()
                campus_id = campuses_map.get(baptist_place)
                
                if not campus_id:
                    members_skipped += 1
                    continue
                
                # Handle family grouping
                kk_name = row.get('kk_name', '').strip()
                family_group_id = None
                
                if kk_name:
                    if kk_name not in family_groups_map:
                        family_groups_map[kk_name] = {}
                    
                    if campus_id not in family_groups_map[kk_name]:
                        # Create new family group
                        fg_id = str(uuid.uuid4())
                        family_group = {
                            "id": fg_id,
                            "group_name": kk_name,
                            "campus_id": campus_id,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }
                        await db.family_groups.insert_one(family_group)
                        family_groups_map[kk_name][campus_id] = fg_id
                    
                    family_group_id = family_groups_map[kk_name][campus_id]
                
                # Parse birth date and calculate age
                birth_date = None
                age = None
                if row.get('birth_date'):
                    try:
                        birth_date = row['birth_date']
                        # Calculate age if birth date exists
                        birth_dt = datetime.fromisoformat(birth_date).date() if isinstance(birth_date, str) else birth_date
                        today = date.today()
                        age = today.year - birth_dt.year - ((today.month, today.day) < (birth_dt.month, birth_dt.day))
                    except:
                        pass
                
                # Create member with all fields
                member = {
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "phone": phone,
                    "campus_id": campus_id,
                    "family_group_id": family_group_id,
                    "external_member_id": row.get('identity_jemaat', '').strip(),
                    "birth_date": birth_date,
                    "age": age,
                    "email": row.get('email', '').strip() or None,
                    "address": row.get('address', '').strip() or None,
                    "category": row.get('category', '').strip() or None,
                    "gender": row.get('gender', '').strip() or None,
                    "blood_type": row.get('blood_type', '').strip() or None,
                    "marital_status": row.get('marital', '').strip() or None,
                    "membership_status": membership_status,
                    "notes": None,
                    "photo_url": None,
                    "last_contact_date": None,
                    "engagement_status": "inactive",
                    "days_since_last_contact": 999,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
                
                await db.members.insert_one(member)
                members_imported += 1
                
                if members_imported % 100 == 0:
                    print(f"  Imported {members_imported} members...")
                    
            except Exception as e:
                print(f"  Error importing member {row.get('name_full')}: {str(e)}")
                members_skipped += 1
    
    print(f"\n✅ Imported {members_imported} members")
    print(f"⚠️  Skipped {members_skipped} members (missing data)")
    print(f"✅ Created {len(family_groups_map)} family groups")
    
    # Step 3: Generate realistic pastoral care data
    print("\n3. Generating realistic pastoral care data...")
    
    # Get all members
    members = await db.members.find({}, {"_id": 0}).to_list(10000)
    print(f"  Found {len(members)} members to generate data for")
    
    # Generate birthday events for members with birth_date
    birthday_count = 0
    for member in members:
        if member.get('birth_date'):
            try:
                birth_date = datetime.fromisoformat(member['birth_date']).date() if isinstance(member['birth_date'], str) else member['birth_date']
                # Create this year's birthday
                this_year_birthday = birth_date.replace(year=2025)
                
                event = {
                    "id": str(uuid.uuid4()),
                    "member_id": member["id"],
                    "campus_id": member["campus_id"],
                    "event_type": "birthday",
                    "event_date": this_year_birthday.isoformat(),
                    "title": f"Ulang Tahun {member['name']}",
                    "description": f"Birthday celebration",
                    "completed": False,
                    "reminder_sent": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
                await db.care_events.insert_one(event)
                birthday_count += 1
            except:
                pass
    
    print(f"  ✓ Generated {birthday_count} birthday events")
    
    # Generate grief support scenarios (5% of members)
    grief_count = 0
    grief_timeline_count = 0
    sample_grief = random.sample(members, min(35, len(members)))
    
    for member in sample_grief:
        # Random grief event in past 6 months
        days_ago = random.randint(30, 180)
        event_date = date.today() - timedelta(days=days_ago)
        mourning_date = event_date + timedelta(days=2)
        
        event_id = str(uuid.uuid4())
        grief_event = {
            "id": event_id,
            "member_id": member["id"],
            "campus_id": member["campus_id"],
            "event_type": "grief_loss",
            "event_date": event_date.isoformat(),
            "title": f"Kehilangan Keluarga - {member['name']}",
            "description": random.choice([
                "Loss of spouse", "Loss of parent", "Loss of child", "Loss of sibling"
            ]),
            "grief_relationship": random.choice(["spouse", "parent", "child", "sibling"]),
            "mourning_service_date": mourning_date.isoformat(),
            "completed": False,
            "reminder_sent": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.care_events.insert_one(grief_event)
        grief_count += 1
        
        # Generate grief timeline (6 stages)
        stages = [
            ("1_week", 7),
            ("2_weeks", 14),
            ("1_month", 30),
            ("3_months", 90),
            ("6_months", 180),
            ("1_year", 365),
        ]
        
        for stage_name, days_offset in stages:
            scheduled_date = mourning_date + timedelta(days=days_offset)
            
            # Randomly complete some past stages
            is_past = scheduled_date < date.today()
            completed = is_past and random.random() < 0.6  # 60% of past stages completed
            
            grief_stage = {
                "id": str(uuid.uuid4()),
                "care_event_id": event_id,
                "member_id": member["id"],
                "campus_id": member["campus_id"],
                "stage": stage_name,
                "scheduled_date": scheduled_date.isoformat(),
                "completed": completed,
                "completed_at": (scheduled_date + timedelta(days=random.randint(0, 3))).isoformat() if completed else None,
                "notes": "Follow-up completed" if completed else None,
                "reminder_sent": completed,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            await db.grief_support.insert_one(grief_stage)
            grief_timeline_count += 1
        
        # Update member's last contact if grief event exists
        if grief_count % 2 == 0:  # Some members contacted recently
            await db.members.update_one(
                {"id": member["id"]},
                {"$set": {
                    "last_contact_date": (date.today() - timedelta(days=random.randint(1, 20))).isoformat(),
                    "engagement_status": "active"
                }}
            )
    
    print(f"  ✓ Generated {grief_count} grief events with {grief_timeline_count} timeline stages")
    
    # Generate hospital visits (3% of members)
    hospital_count = 0
    sample_hospital = random.sample(members, min(20, len(members)))
    
    for member in sample_hospital:
        days_ago = random.randint(5, 60)
        admission_date = date.today() - timedelta(days=days_ago)
        discharge_date = admission_date + timedelta(days=random.randint(2, 10))
        
        hospital_event = {
            "id": str(uuid.uuid4()),
            "member_id": member["id"],
            "campus_id": member["campus_id"],
            "event_type": "hospital_visit",
            "event_date": admission_date.isoformat(),
            "title": f"Kunjungan Rumah Sakit - {member['name']}",
            "description": "Hospital admission",
            "hospital_name": random.choice(["RSU Jakarta", "RS Siloam", "RS Pelni", "RS Harapan Kita"]),
            "admission_date": admission_date.isoformat(),
            "discharge_date": discharge_date.isoformat() if random.random() < 0.7 else None,
            "visitation_log": [{
                "visitor_name": random.choice(["Pastor John", "Pastor Maria", "Pastor David"]),
                "visit_date": (admission_date + timedelta(days=1)).isoformat(),
                "notes": "Visited and prayed with family",
                "prayer_offered": True
            }] if random.random() < 0.8 else [],
            "completed": random.random() < 0.5,
            "reminder_sent": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.care_events.insert_one(hospital_event)
        hospital_count += 1
    
    print(f"  ✓ Generated {hospital_count} hospital visit events")
    
    # Generate financial aid (2% of members)
    aid_count = 0
    sample_aid = random.sample(members, min(15, len(members)))
    
    aid_types = ["education", "medical", "emergency", "housing", "food", "funeral_costs"]
    
    for member in sample_aid:
        days_ago = random.randint(10, 120)
        event_date = date.today() - timedelta(days=days_ago)
        aid_type = random.choice(aid_types)
        
        aid_amounts = {
            "education": random.randint(1000000, 5000000),
            "medical": random.randint(500000, 3000000),
            "emergency": random.randint(1000000, 4000000),
            "housing": random.randint(2000000, 8000000),
            "food": random.randint(500000, 1500000),
            "funeral_costs": random.randint(3000000, 10000000)
        }
        
        aid_event = {
            "id": str(uuid.uuid4()),
            "member_id": member["id"],
            "campus_id": member["campus_id"],
            "event_type": "financial_aid",
            "event_date": event_date.isoformat(),
            "title": f"Bantuan Keuangan - {member['name']}",
            "aid_type": aid_type,
            "aid_amount": aid_amounts[aid_type],
            "aid_notes": f"{aid_type.replace('_', ' ').title()} assistance provided",
            "completed": True,
            "reminder_sent": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.care_events.insert_one(aid_event)
        aid_count += 1
        
        # Update last contact for aided members
        await db.members.update_one(
            {"id": member["id"]},
            {"$set": {
                "last_contact_date": event_date.isoformat(),
                "engagement_status": "active"
            }}
        )
    
    print(f"  ✓ Generated {aid_count} financial aid events")
    
    # Generate regular contact events (10% of members)
    contact_count = 0
    sample_contact = random.sample(members, min(70, len(members)))
    
    for member in sample_contact:
        days_ago = random.randint(1, 45)
        event_date = date.today() - timedelta(days=days_ago)
        
        contact_event = {
            "id": str(uuid.uuid4()),
            "member_id": member["id"],
            "campus_id": member["campus_id"],
            "event_type": "regular_contact",
            "event_date": event_date.isoformat(),
            "title": f"Kontak Rutin - {member['name']}",
            "description": random.choice([
                "Phone call check-in",
                "Home visit",
                "Post-service conversation",
                "Prayer meeting"
            ]),
            "completed": True,
            "reminder_sent": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.care_events.insert_one(contact_event)
        contact_count += 1
        
        # Update last contact
        await db.members.update_one(
            {"id": member["id"]},
            {"$set": {
                "last_contact_date": event_date.isoformat(),
                "engagement_status": "active" if days_ago < 30 else ("at_risk" if days_ago < 60 else "inactive"),
                "days_since_last_contact": days_ago
            }}
        )
    
    print(f"  ✓ Generated {contact_count} regular contact events")
    
    # Step 4: Summary
    print("\n" + "="*60)
    print("IMPORT SUMMARY")
    print("="*60)
    print(f"✅ Campuses created: {len(campuses_map)}")
    print(f"✅ Members imported: {members_imported}")
    print(f"✅ Family groups created: {len(family_groups_map)}")
    print(f"✅ Birthday events: {birthday_count}")
    print(f"✅ Grief events: {grief_count} (with {grief_timeline_count} timeline stages)")
    print(f"✅ Hospital events: {hospital_count}")
    print(f"✅ Financial aid events: {aid_count}")
    print(f"✅ Regular contact events: {contact_count}")
    print(f"\n🎉 Data import completed successfully!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(import_campuses_and_data())
