"""
Pydantic schemas for waitlist.
"""

from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional
from datetime import datetime
from uuid import UUID


class WaitlistCreate(BaseModel):
    """Schema for creating a new waitlist entry"""

    email: EmailStr = Field(..., description="User's email address")

    @validator("email")
    def validate_email(cls, v):
        """Validate email format and normalize"""
        return v.lower().strip()


class WaitlistResponse(BaseModel):
    """Schema for waitlist entry response"""

    id: UUID
    email: str
    status: str
    access_code: Optional[str] = None
    created_at: datetime
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WaitlistApprove(BaseModel):
    """Schema for approving a waitlist entry"""

    send_email: bool = Field(
        True, description="Whether to send access code email to the user"
    )


class WaitlistReject(BaseModel):
    """Schema for rejecting a waitlist entry"""

    reason: Optional[str] = Field(None, max_length=500, description="Rejection reason")


class WaitlistListResponse(BaseModel):
    """Schema for paginated waitlist list response"""

    items: list[WaitlistResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class WaitlistMessageResponse(BaseModel):
    """Schema for simple message responses"""

    message: str
    email: Optional[str] = None
    access_code: Optional[str] = None
