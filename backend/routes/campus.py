"""Campus routes"""
from litestar import get, post, put, Request
from litestar.exceptions import HTTPException
from litestar.response import Response as LitestarResponse
from datetime import datetime, timezone
import logging

from dependencies import get_db, get_current_user
from models import Campus, CampusCreate, to_mongo_doc
from enums import UserRole
from utils import get_from_cache, set_in_cache, invalidate_cache

logger = logging.getLogger(__name__)

def safe_error_detail(e: Exception) -> str:
    return str(e) if str(e) else "Internal server error"


@post("/campuses")
async def create_campus(data: CampusCreate, request: Request) -> dict:
    """Create a new campus (full admin only)"""
    db = get_db()
    current_user = await get_current_user(request)
    if current_user.get("role") != UserRole.FULL_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only full administrators can create campuses")
    try:
        campus_obj = Campus(
            campus_name=data.campus_name,
            location=data.location,
            timezone=data.timezone
        )
        await db.campuses.insert_one(to_mongo_doc(campus_obj))
        invalidate_cache("campuses:")
        return {"id": campus_obj.id, "campus_name": campus_obj.campus_name, "location": campus_obj.location}
    except Exception as e:
        logger.error(f"Error creating campus: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/campuses")
async def list_campuses() -> list:
    """List all campuses (public for login selection) - cached"""
    db = get_db()
    cache_key = "campuses:all"
    cached = get_from_cache(cache_key, ttl_seconds=600)
    cache_headers = {"Cache-Control": "public, max-age=300", "Vary": "Accept-Encoding"}

    if cached is not None:
        return LitestarResponse(content=cached, headers=cache_headers)

    try:
        campuses = await db.campuses.find({"is_active": True}, {"_id": 0}).to_list(100)
        serialized = []
        for c in campuses:
            cc = dict(c)
            if isinstance(cc.get('created_at'), datetime):
                cc['created_at'] = cc['created_at'].isoformat()
            if isinstance(cc.get('updated_at'), datetime):
                cc['updated_at'] = cc['updated_at'].isoformat()
            serialized.append(cc)
        set_in_cache(cache_key, serialized)
        return LitestarResponse(content=serialized, headers=cache_headers)
    except Exception as e:
        logger.error(f"Error listing campuses: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


async def _get_campus_by_id(campus_id: str) -> dict:
    db = get_db()
    campus = await db.campuses.find_one({"id": campus_id}, {"_id": 0})
    if not campus:
        raise HTTPException(status_code=404, detail="Campus not found")
    return campus


@get("/campuses/{campus_id:str}")
async def get_campus(campus_id: str) -> dict:
    """Get campus by ID"""
    try:
        return await _get_campus_by_id(campus_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campus: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@put("/campuses/{campus_id:str}")
async def update_campus(campus_id: str, data: CampusCreate, request: Request) -> dict:
    """Update campus (full admin only)"""
    db = get_db()
    current_user = await get_current_user(request)
    if current_user.get("role") != UserRole.FULL_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only full administrators can update campuses")
    try:
        result = await db.campuses.update_one(
            {"id": campus_id},
            {"$set": {**to_mongo_doc(data), "updated_at": datetime.now(timezone.utc)}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Campus not found")
        invalidate_cache("campuses:")
        return await _get_campus_by_id(campus_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating campus: {str(e)}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


# Route handlers to register with Litestar app
route_handlers = [create_campus, list_campuses, get_campus, update_campus]
