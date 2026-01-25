"""
Leads API for capturing interested users.
"""

import re
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from loguru import logger

from app.services.database import mongodb

router = APIRouter(prefix="/leads", tags=["leads"])

# Simple email regex pattern
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


# =============================================================================
# SCHEMAS
# =============================================================================

class LeadSubmission(BaseModel):
    """Lead submission from frontend."""
    parcel_id: str
    name: str
    email: str
    phone: Optional[str] = None
    interests: List[str] = []

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not EMAIL_PATTERN.match(v):
            raise ValueError('Invalid email format')
        return v.lower()


class LeadResponse(BaseModel):
    """Response after lead submission."""
    success: bool
    message: str
    lead_id: Optional[str] = None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("", response_model=LeadResponse)
async def submit_lead(lead: LeadSubmission):
    """Submit a new lead for a parcel.

    Args:
        lead: Lead submission data with name, email, and optional phone/interests

    Returns:
        Success confirmation with lead ID
    """
    try:
        # Get leads collection
        leads_collection = await mongodb.get_collection("leads")
        if leads_collection is None:
            logger.warning("MongoDB not available, lead not saved")
            # Still return success to not break UX, but log warning
            return LeadResponse(
                success=True,
                message="Dziękujemy za zgłoszenie! Skontaktujemy się wkrótce.",
                lead_id=None
            )

        # Create lead document
        lead_doc = {
            "parcel_id": lead.parcel_id,
            "name": lead.name,
            "email": lead.email,
            "phone": lead.phone,
            "interests": lead.interests,
            "created_at": datetime.utcnow(),
            "source": "parcel_details",
            "status": "new",
        }

        # Insert into MongoDB
        result = await leads_collection.insert_one(lead_doc)
        lead_id = str(result.inserted_id)

        logger.info(f"Lead saved: {lead_id} for parcel {lead.parcel_id}")

        return LeadResponse(
            success=True,
            message="Dziękujemy za zgłoszenie! Skontaktujemy się wkrótce.",
            lead_id=lead_id
        )

    except Exception as e:
        logger.error(f"Failed to save lead: {e}")
        raise HTTPException(
            status_code=500,
            detail="Nie udało się zapisać zgłoszenia. Spróbuj ponownie później."
        )


@router.get("/count")
async def get_leads_count():
    """Get total count of leads (for admin/analytics)."""
    try:
        leads_collection = await mongodb.get_collection("leads")
        if leads_collection is None:
            return {"count": 0, "status": "mongodb_unavailable"}

        count = await leads_collection.count_documents({})
        return {"count": count}

    except Exception as e:
        logger.error(f"Failed to get leads count: {e}")
        raise HTTPException(status_code=500, detail=str(e))
