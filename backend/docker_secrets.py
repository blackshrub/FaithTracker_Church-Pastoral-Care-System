import os
from pathlib import Path

SECRETS_DIR = Path(os.environ.get("SECRETS_DIR", "/run/secrets"))


def get_secret(name: str, env_fallback: str | None = None) -> str | None:
    secret_file = SECRETS_DIR / name

    if secret_file.exists():
        try:
            return secret_file.read_text().strip()
        except (OSError, PermissionError):
            pass

    if env_fallback:
        return os.environ.get(env_fallback)

    return None


def get_secret_required(name: str, env_fallback: str | None = None) -> str:
    value = get_secret(name, env_fallback)

    if value is None:
        locations = [f"Docker secret: {SECRETS_DIR / name}"]
        if env_fallback:
            locations.append(f"Environment: {env_fallback}")
        raise RuntimeError(f"Required secret '{name}' not found. Checked: {', '.join(locations)}")

    return value


def get_mongo_password() -> str:
    return get_secret_required("mongo_password", "MONGO_ROOT_PASSWORD")


def get_jwt_secret() -> str:
    return get_secret_required("jwt_secret", "JWT_SECRET_KEY")


def get_encryption_key() -> str:
    return get_secret_required("encryption_key", "ENCRYPTION_KEY")
