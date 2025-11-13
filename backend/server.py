from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import httpx


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore MongoDB's _id field
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

# Integration Test Models
class WhatsAppTestRequest(BaseModel):
    phone: str
    message: str

class WhatsAppTestResponse(BaseModel):
    success: bool
    message: str
    details: Optional[dict] = None

class EmailTestResponse(BaseModel):
    success: bool
    message: str
    pending_provider: bool = False

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

# Integration Test Endpoints
@api_router.post("/integrations/ping/whatsapp", response_model=WhatsAppTestResponse)
async def test_whatsapp_integration(request: WhatsAppTestRequest):
    """Test WhatsApp gateway integration by sending a test message"""
    try:
        whatsapp_url = os.environ.get('WHATSAPP_GATEWAY_URL')
        church_name = os.environ.get('CHURCH_NAME', 'Church')
        
        if not whatsapp_url:
            raise HTTPException(status_code=500, detail="WhatsApp gateway URL not configured")
        
        # Format phone number (ensure it's in the correct format)
        phone_formatted = request.phone
        if not phone_formatted.endswith('@s.whatsapp.net'):
            phone_formatted = f"{request.phone}@s.whatsapp.net"
        
        # Prepare the message payload according to the API documentation
        payload = {
            "phone": phone_formatted,
            "message": request.message
        }
        
        logger.info(f"Sending WhatsApp test message to {phone_formatted}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{whatsapp_url}/send/message",
                json=payload
            )
            
            response_data = response.json()
            logger.info(f"WhatsApp API Response: {response_data}")
            
            # Check if the API returned success
            if response.status_code == 200 and response_data.get('code') == 'SUCCESS':
                return WhatsAppTestResponse(
                    success=True,
                    message=f"✅ WhatsApp message sent successfully to {request.phone}!",
                    details={
                        "message_id": response_data.get('results', {}).get('message_id'),
                        "status": response_data.get('results', {}).get('status'),
                        "phone": phone_formatted
                    }
                )
            else:
                error_msg = response_data.get('message', 'Unknown error')
                return WhatsAppTestResponse(
                    success=False,
                    message=f"❌ Failed to send WhatsApp message: {error_msg}",
                    details=response_data
                )
                
    except httpx.TimeoutException:
        logger.error("WhatsApp gateway timeout")
        return WhatsAppTestResponse(
            success=False,
            message="❌ WhatsApp gateway timeout. Please check if the gateway is running.",
            details={"error": "timeout"}
        )
    except Exception as e:
        logger.error(f"WhatsApp integration error: {str(e)}")
        return WhatsAppTestResponse(
            success=False,
            message=f"❌ Error: {str(e)}",
            details={"error": str(e)}
        )

@api_router.get("/integrations/ping/email", response_model=EmailTestResponse)
async def test_email_integration():
    """Email integration test - currently pending provider configuration"""
    return EmailTestResponse(
        success=False,
        message="📧 Email integration pending provider configuration. Currently WhatsApp-only mode.",
        pending_provider=True
    )

@api_router.get("/integrations/logs")
async def get_integration_logs():
    """Get recent integration test logs"""
    # For now, return a simple placeholder
    # In full implementation, this would query a logs collection
    return {
        "logs": [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "info",
                "message": "Integration endpoints ready. Use POST /api/integrations/ping/whatsapp to test."
            }
        ]
    }

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    # Convert to dict and serialize datetime to ISO string for MongoDB
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    # Exclude MongoDB's _id field from the query results
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    
    # Convert ISO string timestamps back to datetime objects
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()