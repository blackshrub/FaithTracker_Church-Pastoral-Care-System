"""
FaithTracker Member Routes
Handles member CRUD operations, photo uploads, and at-risk member listing
"""

from litestar import get, post, put, delete, Request, Response
from litestar.exceptions import HTTPException
from litestar.datastructures import UploadFile
from litestar.params import Parameter
import msgspec
import logging
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable, Awaitable
from PIL import Image
from pymongo import ReturnDocument

from enums import EngagementStatus, UserRole, ActivityActionType
from constants import MAX_PAGE_NUMBER, MAX_LIMIT, MAX_IMAGE_SIZE
from models import (
    Member, MemberCreate, MemberUpdate,
    to_mongo_doc, is_valid_uuid
)
from utils import (
    normalize_phone_number, validate_phone,
    calculate_engagement_status, escape_regex,
    validate_image_magic_bytes
)
from dependencies import (
    get_db, get_current_user, get_campus_filter, safe_error_detail
)

logger = logging.getLogger(__name__)

# Callbacks to server.py functions (set via init_member_routes)
_invalidate_dashboard_cache: Optional[Callable[[str], Awaitable[None]]] = None
_log_activity: Optional[Callable[..., Awaitable[None]]] = None
_msgspec_enc_hook: Optional[Callable] = None
_root_dir: Optional[str] = None


def init_member_routes(
    invalidate_dashboard_cache: Callable[[str], Awaitable[None]],
    log_activity: Callable[..., Awaitable[None]],
    msgspec_enc_hook: Callable,
    root_dir: str
):
    """Initialize member routes with callbacks to server.py functions"""
    global _invalidate_dashboard_cache, _log_activity, _msgspec_enc_hook, _root_dir
    _invalidate_dashboard_cache = invalidate_dashboard_cache
    _log_activity = log_activity
    _msgspec_enc_hook = msgspec_enc_hook
    _root_dir = root_dir


# ==================== MEMBER ENDPOINTS ====================

@post("/members")
async def create_member(data: MemberCreate, request: Request) -> dict:
    """Create a new member"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        # For campus-specific users, enforce their campus
        campus_id = data.campus_id
        if current_user.get("role") in [UserRole.CAMPUS_ADMIN.value, UserRole.PASTOR.value]:
            campus_id = current_user["campus_id"]

        member_obj = Member(
            name=data.name,
            phone=normalize_phone_number(data.phone) if data.phone else None,
            campus_id=campus_id,
            external_member_id=data.external_member_id,
            notes=data.notes,
            birth_date=data.birth_date,
            address=data.address,
            category=data.category,
            gender=data.gender,
            blood_type=data.blood_type,
            marital_status=data.marital_status,
            membership_status=data.membership_status,
            age=data.age
        )

        member_dict = to_mongo_doc(member_obj)
        await db.members.insert_one(member_dict)

        # Invalidate dashboard cache since member count changed
        if _invalidate_dashboard_cache:
            await _invalidate_dashboard_cache(campus_id)

        return {"id": member_obj.id, "name": member_obj.name, "campus_id": member_obj.campus_id}
    except Exception as e:
        logger.error(f"Error creating member: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/members")
async def list_members(
    request: Request,
    page: int = Parameter(default=1, ge=1, le=MAX_PAGE_NUMBER),
    limit: int = Parameter(default=50, ge=1, le=MAX_LIMIT),
    engagement_status: Optional[EngagementStatus] = None,
    search: Optional[str] = None,
    show_archived: bool = False,
    fields: Optional[str] = None,  # Comma-separated list of fields to return
) -> Response:
    """List all members with pagination"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        query = get_campus_filter(current_user)

        # Exclude archived members by default (unless show_archived=true)
        if not show_archived:
            query["is_archived"] = {"$ne": True}
        else:
            query["is_archived"] = True

        if engagement_status:
            query["engagement_status"] = engagement_status

        if search:
            # Security: Escape regex special characters to prevent NoSQL injection
            safe_search = escape_regex(search)
            query["$or"] = [
                {"name": {"$regex": safe_search, "$options": "i"}},  # Partial name match
                {"phone": {"$regex": safe_search, "$options": "i"}}  # Partial phone match
            ]

        # Calculate skip for pagination
        skip = (page - 1) * limit

        # Get total count for pagination metadata
        total = await db.members.count_documents(query)

        # Build projection based on fields parameter or use default
        if fields:
            # Parse comma-separated fields and build projection
            allowed_fields = {"id", "name", "phone", "campus_id", "photo_url", "last_contact_date",
                            "engagement_status", "days_since_last_contact", "is_archived",
                            "external_member_id", "age", "gender", "category", "membership_status",
                            "marital_status", "blood_type", "birth_date"}
            requested_fields = [f.strip() for f in fields.split(",")]
            projection = {"_id": 0}
            for field in requested_fields:
                if field in allowed_fields:
                    projection[field] = 1
        else:
            # Default projection for list view (exclude heavy fields like notes, address)
            projection = {
                "_id": 0,
                "id": 1,
                "name": 1,
                "phone": 1,
                "campus_id": 1,
                "photo_url": 1,
                "last_contact_date": 1,
                "engagement_status": 1,
                "days_since_last_contact": 1,
                "is_archived": 1,
                "external_member_id": 1,
                "age": 1,
                "gender": 1,
                "category": 1,
                "membership_status": 1,
                "marital_status": 1,
                "blood_type": 1,
                "birth_date": 1
                # Exclude: notes, address, archived_at, archived_reason, etc.
            }

        # Get paginated members with projection
        members = await db.members.find(query, projection).skip(skip).limit(limit).to_list(limit)
        
        # Update engagement status for each member
        for member in members:
            if member.get('last_contact_date'):
                if isinstance(member['last_contact_date'], str):
                    member['last_contact_date'] = datetime.fromisoformat(member['last_contact_date'])

            status, days = calculate_engagement_status(member.get('last_contact_date'))
            member['engagement_status'] = status
            member['days_since_last_contact'] = days

        # Return members array with X-Total-Count header for pagination
        return Response(
            content=msgspec.json.encode(members, enc_hook=_msgspec_enc_hook),
            media_type="application/json",
            headers={"X-Total-Count": str(total)}
        )
        
    except Exception as e:
        logger.error(f"Error listing members: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/members/at-risk")
async def list_at_risk_members(request: Request) -> list:
    """Get members with no contact in 30+ days"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        # Apply campus filter for multi-tenancy
        query = get_campus_filter(current_user)

        # Projection for at-risk members list
        projection = {
            "_id": 0,
            "id": 1,
            "name": 1,
            "phone": 1,
            "campus_id": 1,
            "photo_url": 1,
            "last_contact_date": 1,
            "engagement_status": 1,
            "days_since_last_contact": 1,
            "external_member_id": 1
        }

        members = await db.members.find(query, projection).to_list(1000)

        at_risk_members = []
        for member in members:
            if member.get('last_contact_date'):
                if isinstance(member['last_contact_date'], str):
                    member['last_contact_date'] = datetime.fromisoformat(member['last_contact_date'])

            status, days = calculate_engagement_status(member.get('last_contact_date'))
            member['engagement_status'] = status
            member['days_since_last_contact'] = days

            if status in [EngagementStatus.AT_RISK, EngagementStatus.DISCONNECTED]:
                at_risk_members.append(member)

        # Sort by days descending
        at_risk_members.sort(key=lambda x: x['days_since_last_contact'], reverse=True)

        return at_risk_members
    except Exception as e:
        logger.error(f"Error getting at-risk members: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/members/{member_id:str}")
async def get_member(member_id: str, request: Request) -> dict:
    """Get member by ID"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        # Build query with campus filter for multi-tenancy
        query = {"id": member_id}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        member = await db.members.find_one(query, {"_id": 0})
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        if member.get('last_contact_date'):
            if isinstance(member['last_contact_date'], str):
                member['last_contact_date'] = datetime.fromisoformat(member['last_contact_date'])

        status, days = calculate_engagement_status(member.get('last_contact_date'))
        member['engagement_status'] = status
        member['days_since_last_contact'] = days

        return member
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting member: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@put("/members/{member_id:str}")
async def update_member(member_id: str, data: MemberUpdate, request: Request) -> dict:
    """Update member"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        # Validate UUID format
        if not is_valid_uuid(member_id):
            raise HTTPException(status_code=400, detail="Invalid member ID format")

        # Verify member belongs to user's campus
        query = {"id": member_id}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        update_data = {k: v for k, v in to_mongo_doc(data).items() if v is not None}

        # Validate and normalize phone number if provided
        if 'phone' in update_data and update_data['phone']:
            if not validate_phone(update_data['phone']):
                raise HTTPException(status_code=400, detail="Invalid phone number format")
            update_data['phone'] = normalize_phone_number(update_data['phone'])

        update_data["updated_at"] = datetime.now(timezone.utc)

        # Use find_one_and_update for single roundtrip (optimized from 3 queries to 1)
        updated_member = await db.members.find_one_and_update(
            query,
            {"$set": update_data},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0}
        )

        if not updated_member:
            raise HTTPException(status_code=404, detail="Member not found")

        # Invalidate dashboard cache since member data changed
        if _invalidate_dashboard_cache:
            await _invalidate_dashboard_cache(updated_member.get("campus_id"))

        return updated_member
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating member: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@delete("/members/{member_id:str}", status_code=200)
async def delete_member(member_id: str, request: Request) -> dict:
    """Delete member"""
    current_user = await get_current_user(request)
    db = get_db()
    try:
        # Verify member belongs to user's campus
        query = {"id": member_id}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        member = await db.members.find_one(query, {"_id": 0})
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        result = await db.members.delete_one({"id": member_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Member not found")

        # Also delete related care events and grief support (with campus filter for defense in depth)
        member_campus_id = member.get("campus_id")
        cascade_filter = {"member_id": member_id}
        if member_campus_id:
            cascade_filter["campus_id"] = member_campus_id

        await db.care_events.delete_many(cascade_filter)
        await db.grief_support.delete_many(cascade_filter)
        await db.accident_followup.delete_many(cascade_filter)
        await db.activity_logs.delete_many({"member_id": member_id, "campus_id": member_campus_id} if member_campus_id else {"member_id": member_id})

        # Log activity
        if _log_activity:
            await _log_activity(
                campus_id=member.get("campus_id") or current_user.get("campus_id"),
                user_id=current_user["id"],
                user_name=current_user["name"],
                action_type=ActivityActionType.DELETE_MEMBER,
                member_id=member_id,
                member_name=member.get("name", "Unknown"),
                notes=f"Deleted member {member.get('name', 'Unknown')}",
                user_photo_url=current_user.get("photo_url")
            )

        # Invalidate dashboard cache since member count changed
        if _invalidate_dashboard_cache:
            await _invalidate_dashboard_cache(member.get("campus_id") or current_user.get("campus_id"))

        return {"success": True, "message": "Member deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting member: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/members/{member_id:str}/photo")
async def upload_member_photo(member_id: str, request: Request, data: UploadFile) -> dict:
    """Upload member profile photo with optimization"""
    current_user = await get_current_user(request)
    db = get_db()
    file = data  # Alias for compatibility
    try:
        # Build query with campus filter for multi-tenancy
        query = {"id": member_id}
        campus_filter = get_campus_filter(current_user)
        if campus_filter:
            query.update(campus_filter)

        # Check member exists and belongs to user's campus
        member = await db.members.find_one(query, {"_id": 0})
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        # Read and validate file size
        contents = await file.read()
        if len(contents) > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {MAX_IMAGE_SIZE // (1024*1024)} MB.")

        # Security: Validate image by magic bytes (not just Content-Type which can be spoofed)
        is_valid, result = validate_image_magic_bytes(contents)
        if not is_valid:
            raise HTTPException(status_code=400, detail=result)

        # Process image
        try:
            image = Image.open(io.BytesIO(contents))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid or corrupted image file")
        
        # Optimize image: resize and compress
        image = image.convert('RGB')
        
        # Resize to multiple sizes for different contexts
        sizes = {
            'thumbnail': (100, 100),  # For lists and small avatars
            'medium': (300, 300),     # For profile views
            'large': (600, 600)       # For detailed views
        }
        
        base_filename = f"{member_id}"
        photo_urls = {}
        
        for size_name, (width, height) in sizes.items():
            # Create optimized version
            resized = image.copy()
            resized.thumbnail((width, height), Image.Resampling.LANCZOS)
            
            # Save with optimization (progressive JPEG for faster loading)
            filename = f"{base_filename}_{size_name}.jpg"
            filepath = Path(_root_dir or ".") / "uploads" / filename
            resized.save(filepath, "JPEG", quality=85, optimize=True, progressive=True)
            
            photo_urls[size_name] = f"/uploads/{filename}"
        
        # Update member record with optimized photo URLs
        await db.members.update_one(
            {"id": member_id},
            {"$set": {
                "photo_url": photo_urls['medium'],  # Default medium size
                "photo_urls": photo_urls,  # All sizes available
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        return {
            "success": True, 
            "photo_urls": photo_urls,
            "default_url": photo_urls['medium']
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading photo: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


# Route handlers list for server.py to include
route_handlers = [
    create_member,
    list_members,
    list_at_risk_members,
    get_member,
    update_member,
    delete_member,
    upload_member_photo,
]
