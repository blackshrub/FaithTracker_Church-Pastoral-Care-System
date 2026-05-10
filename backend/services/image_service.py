import asyncio
import io
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

_thread_pool = ThreadPoolExecutor(max_workers=4)

MEMBER_PHOTO_SIZES = {
    "thumbnail": (100, 100),
    "medium": (300, 300),
    "large": (600, 600),
}

USER_PHOTO_SIZE = (400, 400)

JPEG_QUALITY = 85

# Cap pixel count to defend against decompression bombs.
# A few-MB JPEG can expand to hundreds of millions of pixels and exhaust
# worker memory before the resize call. 40 MP comfortably covers any phone
# camera shot while rejecting maliciously-crafted payloads.
MAX_IMAGE_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def _open_image_safely(image_bytes: bytes) -> Image.Image:
    """Open with explicit pixel-count guard.

    PIL only raises DecompressionBombError when MAX_IMAGE_PIXELS is exceeded
    AT decode time, but the size is known from the header — fail fast before
    decoding to avoid the memory spike.

    Multi-frame images (animated GIF, animated WebP) are rejected outright:
    the per-frame pixel check would let a 100-frame 6000x6000 GIF pass
    (each frame at 36 MP) but require 3.6 GB to fully decode. Member and
    user photos have no use for animation.
    """
    img = Image.open(io.BytesIO(image_bytes))
    n_frames = getattr(img, "n_frames", 1)
    if n_frames > 1:
        raise ValueError(
            f"Animated images are not allowed ({n_frames} frames). "
            "Use a still image (JPEG, PNG, or single-frame WebP)."
        )
    width, height = img.size
    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError(
            f"Image too large: {width}x{height} ({width * height:,} pixels) "
            f"exceeds limit of {MAX_IMAGE_PIXELS:,} pixels"
        )
    img.load()  # decode now (still inside the guarded path)
    return img


class ImageService:
    @staticmethod
    def _process_image_sync(
        image_bytes: bytes, sizes: dict[str, tuple[int, int]], output_path_base: Path, quality: int = JPEG_QUALITY
    ) -> dict[str, str]:
        results = {}

        img = _open_image_safely(image_bytes)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        for size_name, (width, height) in sizes.items():
            resized = img.copy()
            resized.thumbnail((width, height), Image.Resampling.LANCZOS)

            output_path = output_path_base.parent / f"{output_path_base.stem}_{size_name}.jpg"

            resized.save(output_path, "JPEG", quality=quality, optimize=True, progressive=True)

            results[size_name] = str(output_path.relative_to(UPLOAD_DIR))

        return results

    @staticmethod
    def _process_single_image_sync(
        image_bytes: bytes, size: tuple[int, int], output_path: Path, quality: int = JPEG_QUALITY
    ) -> str:
        img = _open_image_safely(image_bytes)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img.thumbnail(size, Image.Resampling.LANCZOS)

        img.save(output_path, "JPEG", quality=quality, optimize=True, progressive=True)

        return str(output_path.relative_to(UPLOAD_DIR))

    @classmethod
    async def process_member_photo(cls, image_bytes: bytes, member_id: str, church_id: str) -> dict[str, str]:
        output_dir = UPLOAD_DIR / "members" / church_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path_base = output_dir / member_id

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            _thread_pool, cls._process_image_sync, image_bytes, MEMBER_PHOTO_SIZES, output_path_base, JPEG_QUALITY
        )

        logger.info(f"Processed member photo {member_id}: {list(results.keys())}")
        return results

    @classmethod
    async def process_user_photo(cls, image_bytes: bytes, user_id: str) -> str:
        output_dir = UPLOAD_DIR / "users"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{user_id}.jpg"

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _thread_pool, cls._process_single_image_sync, image_bytes, USER_PHOTO_SIZE, output_path, JPEG_QUALITY
        )

        logger.info(f"Processed user photo {user_id}")
        return result

    @classmethod
    async def process_member_photo_background(cls, image_bytes: bytes, member_id: str, church_id: str, db) -> None:
        try:
            results = await cls.process_member_photo(image_bytes, member_id, church_id)

            photo_url = f"/uploads/members/{church_id}/{member_id}_medium.jpg"

            await db.members.update_one(
                {"id": member_id, "church_id": church_id}, {"$set": {"photo_url": photo_url, "photo_sizes": results}}
            )

            logger.info(f"Updated member {member_id} photo URL")

        except Exception as e:
            logger.error(f"Background photo processing failed for member {member_id}: {e}")

    @classmethod
    async def process_user_photo_background(cls, image_bytes: bytes, user_id: str, db) -> None:
        try:
            await cls.process_user_photo(image_bytes, user_id)

            photo_url = f"/uploads/users/{user_id}.jpg"

            await db.users.update_one({"id": user_id}, {"$set": {"photo_url": photo_url}})

            logger.info(f"Updated user {user_id} photo URL")

        except Exception as e:
            logger.error(f"Background photo processing failed for user {user_id}: {e}")

    @staticmethod
    def delete_member_photos(member_id: str, church_id: str) -> bool:
        output_dir = UPLOAD_DIR / "members" / church_id
        deleted = False

        for size_name in MEMBER_PHOTO_SIZES:
            photo_path = output_dir / f"{member_id}_{size_name}.jpg"
            if photo_path.exists():
                photo_path.unlink()
                deleted = True

        return deleted

    @staticmethod
    def delete_user_photo(user_id: str) -> bool:
        photo_path = UPLOAD_DIR / "users" / f"{user_id}.jpg"
        if photo_path.exists():
            photo_path.unlink()
            return True
        return False
