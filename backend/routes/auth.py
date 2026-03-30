"""
FaithTracker Auth Routes - Authentication and user management endpoints
"""

import io
import logging
from datetime import UTC, datetime
from pathlib import Path

from litestar import Request, delete, get, post, put
from litestar.datastructures import UploadFile
from litestar.exceptions import HTTPException
from litestar.status_codes import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_429_TOO_MANY_REQUESTS,
)
from PIL import Image

from constants import MAX_IMAGE_SIZE
from dependencies import (
    check_login_rate_limit,
    clear_login_attempts,
    create_access_token,
    get_client_ip,
    get_current_admin,
    get_current_user,
    get_db,
    get_password_hash,
    record_failed_login,
    safe_error_detail,
    verify_password,
)
from enums import UserRole
from models import (
    PasswordChange,
    ProfileUpdate,
    TokenResponse,
    User,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    to_mongo_doc,
)
from utils import normalize_phone_number, validate_email, validate_image_magic_bytes, validate_password_strength

logger = logging.getLogger(__name__)

# ROOT_DIR for photo uploads
ROOT_DIR = Path(__file__).parent.parent


# ==================== AUTHENTICATION ENDPOINTS ====================


@post("/auth/register")
async def register_user(data: UserCreate, request: Request) -> dict:
    """Register a new user (admin only)"""
    db = get_db()
    try:
        # Validate email format
        if not validate_email(data.email):
            raise HTTPException(status_code=400, detail="Invalid email format")

        # Validate password strength (security requirement)
        is_valid_password, password_error = validate_password_strength(data.password)
        if not is_valid_password:
            raise HTTPException(status_code=400, detail=password_error)

        # Check if email already exists
        existing = await db.users.find_one({"email": data.email}, {"_id": 0})
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Validate campus_id for non-full-admin users
        if data.role != UserRole.FULL_ADMIN and not data.campus_id:
            raise HTTPException(status_code=400, detail="campus_id required for campus admin and pastor roles")

        user = User(
            email=data.email,
            name=data.name,
            role=data.role,
            campus_id=data.campus_id,
            phone=normalize_phone_number(data.phone),
            hashed_password=get_password_hash(data.password),
        )

        await db.users.insert_one(to_mongo_doc(user))

        campus_name = None
        if user.campus_id:
            campus = await db.campuses.find_one({"id": user.campus_id}, {"_id": 0})
            campus_name = campus["campus_name"] if campus else None

        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            campus_id=user.campus_id,
            campus_name=campus_name,
            phone=user.phone,
            is_active=user.is_active,
            created_at=user.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {e!s}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/auth/login")
async def login(data: UserLogin, request: Request) -> dict:
    """Login and get access token with brute force protection.

    Security features:
    - Rate limited: 5 failed attempts per 5 minutes per IP+email
    - Account lockout: 15 minutes after 5 failed attempts
    - Same error message for invalid email/password (prevents enumeration)
    """
    db = get_db()
    client_ip = get_client_ip(request)

    # Check rate limit BEFORE processing login (DragonflyDB-backed, TTL handles cleanup)
    is_allowed, error_msg = await check_login_rate_limit(client_ip, data.email)
    if not is_allowed:
        raise HTTPException(status_code=HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    try:
        user = await db.users.find_one({"email": data.email}, {"_id": 0})
        if not user:
            # Record failed attempt (user not found)
            await record_failed_login(client_ip, data.email)
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

        if not verify_password(data.password, user["hashed_password"]):
            # Record failed attempt (wrong password)
            await record_failed_login(client_ip, data.email)
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

        if not user.get("is_active", True):
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="User account is disabled")

        # For campus-specific users, validate campus_id
        if (
            user.get("role") in [UserRole.CAMPUS_ADMIN.value, UserRole.PASTOR.value]
            and data.campus_id
            and user["campus_id"] != data.campus_id
        ):
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="You don't have access to this campus")

        # For full admins, use the selected campus_id from login
        active_campus_id = user.get("campus_id")
        if user.get("role") == UserRole.FULL_ADMIN.value:
            if data.campus_id:
                # Full admin selected a specific campus
                active_campus_id = data.campus_id
                # Update user's active campus
                await db.users.update_one(
                    {"id": user["id"]}, {"$set": {"campus_id": data.campus_id, "updated_at": datetime.now(UTC)}}
                )
            else:
                raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Please select a campus to continue")

        # Clear failed attempts on successful login
        await clear_login_attempts(client_ip, data.email)

        access_token = create_access_token(data={"sub": user["id"]})

        campus_name = None
        if active_campus_id:
            campus = await db.campuses.find_one({"id": active_campus_id}, {"_id": 0})
            campus_name = campus["campus_name"] if campus else None

        logger.info(f"Successful login for {data.email} from {client_ip}")

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse(
                id=user["id"],
                email=user["email"],
                name=user["name"],
                role=user["role"],
                campus_id=active_campus_id,
                campus_name=campus_name,
                phone=user["phone"],
                is_active=user.get("is_active", True),
                created_at=user["created_at"],
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging in: {e!s}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@get("/auth/me")
async def get_current_user_info(request: Request) -> dict:
    """Get current logged-in user info"""
    db = get_db()
    current_user = await get_current_user(request)
    campus_name = None
    if current_user.get("campus_id"):
        campus = await db.campuses.find_one({"id": current_user["campus_id"]}, {"_id": 0})
        campus_name = campus["campus_name"] if campus else None

    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user["name"],
        role=current_user["role"],
        campus_id=current_user.get("campus_id"),
        campus_name=campus_name,
        phone=current_user["phone"],
        is_active=current_user.get("is_active", True),
        created_at=current_user["created_at"],
    )


@get("/users")
async def list_users(request: Request) -> list:
    """List all users (admin only) - optimized with $lookup to avoid N+1 queries"""
    db = get_db()
    current_admin = await get_current_admin(request)
    try:
        query = {}
        # Campus admins only see users in their campus
        if current_admin.get("role") == UserRole.CAMPUS_ADMIN.value:
            query["campus_id"] = current_admin["campus_id"]

        # Use aggregation pipeline with $lookup for campus name (avoids N+1 queries)
        pipeline = [
            {"$match": query},
            # Only fetch required fields (exclude hashed_password for security)
            {
                "$project": {
                    "_id": 0,
                    "id": 1,
                    "email": 1,
                    "name": 1,
                    "role": 1,
                    "campus_id": 1,
                    "phone": 1,
                    "is_active": 1,
                    "created_at": 1,
                    "photo_url": 1,
                }
            },
            # Lookup campus name
            {
                "$lookup": {
                    "from": "campuses",
                    "localField": "campus_id",
                    "foreignField": "id",
                    "as": "campus_info",
                    "pipeline": [{"$project": {"campus_name": 1, "_id": 0}}],
                }
            },
            # Flatten campus_info array
            {"$addFields": {"campus_name": {"$arrayElemAt": ["$campus_info.campus_name", 0]}}},
            {"$project": {"campus_info": 0}},
            {"$limit": 100},
        ]

        users = await db.users.aggregate(pipeline).to_list(100)

        # Convert to UserResponse (is_active defaults to True if not present)
        result = [
            UserResponse(
                id=u["id"],
                email=u["email"],
                name=u["name"],
                role=u["role"],
                campus_id=u.get("campus_id"),
                campus_name=u.get("campus_name"),
                phone=u["phone"],
                is_active=u.get("is_active", True),
                created_at=u["created_at"],
            )
            for u in users
        ]

        return result
    except Exception as e:
        logger.error(f"Error listing users: {e!s}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@put("/users/{user_id:str}")
async def update_user(user_id: str, data: UserUpdate, request: Request) -> dict:
    """Update a user (full admin only)"""
    db = get_db()
    current_user = await get_current_user(request)
    if current_user["role"] != "full_admin":
        raise HTTPException(status_code=403, detail="Only full administrators can update users")

    try:
        update_data = {k: v for k, v in to_mongo_doc(data).items() if v is not None}

        # Normalize phone number if provided
        if update_data.get("phone"):
            update_data["phone"] = normalize_phone_number(update_data["phone"])

        # Hash password if provided (with strength validation)
        if "password" in update_data:
            is_valid_password, password_error = validate_password_strength(update_data["password"])
            if not is_valid_password:
                raise HTTPException(status_code=400, detail=password_error)
            update_data["hashed_password"] = get_password_hash(update_data["password"])
            del update_data["password"]

        update_data["updated_at"] = datetime.now(UTC)

        result = await db.users.update_one({"id": user_id}, {"$set": update_data})

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")

        updated_user = await db.users.find_one({"id": user_id}, {"_id": 0})

        # Get campus name if campus_id exists
        if updated_user.get("campus_id"):
            campus = await db.campuses.find_one({"id": updated_user["campus_id"]}, {"_id": 0})
            updated_user["campus_name"] = campus["campus_name"] if campus else None

        return updated_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {e!s}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@put("/auth/profile")
async def update_own_profile(data: ProfileUpdate, request: Request) -> dict:
    """Update own profile (all users can update their own name, email, phone)"""
    db = get_db()
    current_user = await get_current_user(request)
    try:
        update_data = {k: v for k, v in to_mongo_doc(data).items() if v is not None}

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Normalize phone number if provided
        if update_data.get("phone"):
            update_data["phone"] = normalize_phone_number(update_data["phone"])

        # Check if email is being changed and if it's already taken
        if "email" in update_data and update_data["email"] != current_user.get("email"):
            existing = await db.users.find_one({"email": update_data["email"], "id": {"$ne": current_user["id"]}})
            if existing:
                raise HTTPException(status_code=400, detail="Email already in use")

        update_data["updated_at"] = datetime.now(UTC)

        result = await db.users.update_one({"id": current_user["id"]}, {"$set": update_data})

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")

        updated_user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0, "hashed_password": 0})

        # Get campus name if campus_id exists
        if updated_user.get("campus_id"):
            campus = await db.campuses.find_one({"id": updated_user["campus_id"]}, {"_id": 0})
            updated_user["campus_name"] = campus["campus_name"] if campus else None

        return updated_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {e!s}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/auth/change-password")
async def change_password(data: PasswordChange, request: Request) -> dict:
    """Change own password (all users)"""
    db = get_db()
    current_user = await get_current_user(request)
    try:
        # Get user with hashed password
        user = await db.users.find_one({"id": current_user["id"]})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Verify current password
        if not verify_password(data.current_password, user["hashed_password"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        # Validate new password strength (security requirement)
        is_valid_password, password_error = validate_password_strength(data.new_password)
        if not is_valid_password:
            raise HTTPException(status_code=400, detail=password_error)

        # Ensure new password is different from current
        if verify_password(data.new_password, user["hashed_password"]):
            raise HTTPException(status_code=400, detail="New password must be different from current password")

        # Hash and update password
        new_hashed = get_password_hash(data.new_password)

        await db.users.update_one(
            {"id": current_user["id"]}, {"$set": {"hashed_password": new_hashed, "updated_at": datetime.now(UTC)}}
        )

        return {"message": "Password changed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing password: {e!s}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@post("/users/{user_id:str}/photo")
async def upload_user_photo(user_id: str, request: Request, data: UploadFile) -> dict:
    """Upload user profile photo"""
    db = get_db()
    current_user = await get_current_user(request)
    file = data  # Alias for compatibility
    # Users can upload their own photo or full admin can upload for others
    if current_user["id"] != user_id and current_user["role"] != "full_admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        # Validate file size
        contents = await file.read()
        if len(contents) > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=400, detail=f"File too large. Maximum size is {MAX_IMAGE_SIZE // (1024 * 1024)} MB."
            )

        # Security: Validate image by magic bytes (not just Content-Type which can be spoofed)
        is_valid, result = validate_image_magic_bytes(contents)
        if not is_valid:
            raise HTTPException(status_code=400, detail=result)

        # Create uploads directory if not exists
        upload_dir = ROOT_DIR / "user_photos"
        upload_dir.mkdir(exist_ok=True)

        # Generate filename - always save as jpg since we convert to RGB
        filename = f"USER-{user_id[:8]}.jpg"
        filepath = upload_dir / filename

        # Resize image to 400x400 and optimize
        try:
            img = Image.open(io.BytesIO(contents))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid or corrupted image file")
        img = img.convert("RGB")
        img.thumbnail((400, 400), Image.Resampling.LANCZOS)
        try:
            img.save(filepath, "JPEG", quality=85, optimize=True, progressive=True)
        except OSError as e:
            logger.error(f"Failed to save user photo: {e!s}")
            raise HTTPException(status_code=507, detail="Failed to save photo. Disk may be full.")

        # Update user record
        photo_url = f"/api/user-photos/{filename}"
        await db.users.update_one({"id": user_id}, {"$set": {"photo_url": photo_url, "updated_at": datetime.now(UTC)}})

        return {"message": "Photo uploaded successfully", "photo_url": photo_url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading user photo: {e!s}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


@delete("/users/{user_id:str}", status_code=200)
async def delete_user(user_id: str, request: Request) -> dict:
    """Delete a user (admin only)"""
    db = get_db()
    current_admin = await get_current_admin(request)
    try:
        # Prevent deleting self
        if user_id == current_admin["id"]:
            raise HTTPException(status_code=400, detail="Cannot delete your own account")

        result = await db.users.delete_one({"id": user_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="User not found")

        return {"success": True, "message": "User deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e!s}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e))


# Export route handlers
route_handlers = [
    register_user,
    login,
    get_current_user_info,
    list_users,
    update_user,
    update_own_profile,
    change_password,
    upload_user_photo,
    delete_user,
]
