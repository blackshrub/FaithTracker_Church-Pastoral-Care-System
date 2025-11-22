"""
Configuration validation for FaithTracker
Validates required environment variables on startup
"""

import os
import sys
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Required environment variables
REQUIRED_ENV_VARS = [
    "MONGO_URL",
    "DB_NAME",
    "JWT_SECRET_KEY",
]

# Production-critical environment variables
PRODUCTION_ENV_VARS = [
    ("CORS_ORIGINS", lambda v: v != '*', "CORS_ORIGINS should not be '*' in production"),
    ("ENCRYPTION_KEY", lambda v: v and len(v) > 32, "ENCRYPTION_KEY must be set and strong"),
]


def validate_config(exit_on_error=True):
    """
    Validate required environment variables

    Args:
        exit_on_error: If True, exit the program on validation failure

    Returns:
        tuple: (is_valid: bool, errors: list, warnings: list)
    """
    errors = []
    warnings = []

    # Check required variables
    for var in REQUIRED_ENV_VARS:
        value = os.getenv(var)
        if not value:
            errors.append(f"Missing required environment variable: {var}")

    # Check production variables
    for var_name, validator, message in PRODUCTION_ENV_VARS:
        value = os.getenv(var_name)
        if value and not validator(value):
            warnings.append(f"⚠️  {message}")
        elif not value:
            warnings.append(f"⚠️  {var_name} is not set")

    # Print results
    if errors:
        print("❌ Configuration Error!")
        print("\nMissing required environment variables:")
        for error in errors:
            print(f"  • {error}")
        print("\nPlease check your .env file and ensure all required variables are set.")

        if exit_on_error:
            sys.exit(1)

    if warnings:
        print("\n⚠️  Configuration Warnings:")
        for warning in warnings:
            print(f"  {warning}")
        print()

    if not errors and not warnings:
        print("✅ Configuration validated successfully")

    return (len(errors) == 0, errors, warnings)


def get_config():
    """Get configuration dictionary"""
    return {
        "mongo_url": os.getenv("MONGO_URL"),
        "db_name": os.getenv("DB_NAME", "pastoral_care_db"),
        "jwt_secret": os.getenv("JWT_SECRET_KEY"),
        "encryption_key": os.getenv("ENCRYPTION_KEY"),
        "cors_origins": os.getenv("CORS_ORIGINS", "*").split(","),
        "church_name": os.getenv("CHURCH_NAME", "GKBJ"),
        "whatsapp_gateway_url": os.getenv("WHATSAPP_GATEWAY_URL"),
        "backend_port": int(os.getenv("BACKEND_PORT", "8001")),
    }


if __name__ == "__main__":
    validate_config()

    print("\nCurrent configuration:")
    config = get_config()
    for key, value in config.items():
        # Mask sensitive values
        if "secret" in key.lower() or "key" in key.lower():
            display_value = f"{value[:8]}..." if value else "Not set"
        else:
            display_value = value
        print(f"  {key}: {display_value}")
