"""
Pydantic schemas for admin functionality
"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime
from typing import Optional, Any
from uuid import UUID


# Admin Settings Schemas
class AdminSettingBase(BaseModel):
    """Base schema for admin settings"""
    key: str = Field(..., description="Unique setting key")
    value: Any = Field(..., description="Setting value (will be stored as JSONB)")
    value_type: str = Field(..., description="Type of value: 'string', 'number', 'boolean', 'json'")
    is_secret: bool = Field(default=False, description="Whether this is a secret value (will be encrypted)")
    description: Optional[str] = Field(None, description="Description of what this setting does")
    category: Optional[str] = Field(None, description="Category: 'api_keys', 'openai', 'email', 'features'")

    @field_validator('value_type')
    @classmethod
    def validate_value_type(cls, v: str) -> str:
        """Validate that value_type is one of the allowed types"""
        allowed_types = ['string', 'number', 'boolean', 'json']
        if v not in allowed_types:
            raise ValueError(f"value_type must be one of {allowed_types}")
        return v

    @field_validator('category')
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        """Validate that category is one of the allowed categories"""
        if v is None:
            return v
        allowed_categories = ['api_keys', 'openai', 'email', 'features', 'system']
        if v not in allowed_categories:
            raise ValueError(f"category must be one of {allowed_categories}")
        return v


class AdminSettingCreate(AdminSettingBase):
    """Schema for creating a new admin setting"""
    pass


class AdminSettingUpdate(BaseModel):
    """Schema for updating an admin setting"""
    value: Optional[Any] = None
    value_type: Optional[str] = None
    is_secret: Optional[bool] = None
    description: Optional[str] = None
    category: Optional[str] = None


class AdminSettingResponse(AdminSettingBase):
    """Schema for admin setting response"""
    id: UUID
    updated_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Admin Audit Log Schemas
class AdminAuditLogBase(BaseModel):
    """Base schema for audit logs"""
    action: str = Field(..., description="Action performed")
    resource_type: Optional[str] = Field(None, description="Type of resource affected")
    resource_id: Optional[str] = Field(None, description="ID of resource affected")
    details: Optional[dict] = Field(None, description="Additional details about the action")
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    severity: Optional[str] = Field(None, description="Severity: 'info', 'warning', 'critical'")

    @field_validator('severity')
    @classmethod
    def validate_severity(cls, v: Optional[str]) -> Optional[str]:
        """Validate severity level"""
        if v is None:
            return v
        allowed_severities = ['info', 'warning', 'critical']
        if v not in allowed_severities:
            raise ValueError(f"severity must be one of {allowed_severities}")
        return v


class AdminAuditLogCreate(AdminAuditLogBase):
    """Schema for creating an audit log entry"""
    user_id: Optional[UUID] = None


class AdminAuditLogResponse(AdminAuditLogBase):
    """Schema for audit log response"""
    id: UUID
    user_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Application Log Schemas
class ApplicationLogBase(BaseModel):
    """Base schema for application logs"""
    level: str = Field(..., description="Log level: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'")
    logger_name: Optional[str] = None
    message: str = Field(..., description="Log message")
    module: Optional[str] = None
    function_name: Optional[str] = None
    line_number: Optional[int] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    stack_trace: Optional[str] = None
    context: Optional[dict] = None

    @field_validator('level')
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate log level"""
        allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v not in allowed_levels:
            raise ValueError(f"level must be one of {allowed_levels}")
        return v


class ApplicationLogCreate(ApplicationLogBase):
    """Schema for creating an application log entry"""
    pass


class ApplicationLogResponse(ApplicationLogBase):
    """Schema for application log response"""
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Security Event Schemas
class SecurityEventBase(BaseModel):
    """Base schema for security events"""
    event_type: str = Field(..., description="Event type: 'brute_force', 'suspicious_activity', etc.")
    user_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[dict] = None
    severity: Optional[str] = Field(None, description="Severity: 'low', 'medium', 'high', 'critical'")

    @field_validator('severity')
    @classmethod
    def validate_severity(cls, v: Optional[str]) -> Optional[str]:
        """Validate severity level"""
        if v is None:
            return v
        allowed_severities = ['low', 'medium', 'high', 'critical']
        if v not in allowed_severities:
            raise ValueError(f"severity must be one of {allowed_severities}")
        return v


class SecurityEventCreate(SecurityEventBase):
    """Schema for creating a security event"""
    pass


class SecurityEventUpdate(BaseModel):
    """Schema for updating a security event"""
    is_resolved: Optional[bool] = None
    resolved_at: Optional[datetime] = None


class SecurityEventResponse(SecurityEventBase):
    """Schema for security event response"""
    id: UUID
    is_resolved: bool
    resolved_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# List response schemas
class PaginatedResponse(BaseModel):
    """Generic paginated response"""
    total: int
    page: int
    page_size: int
    total_pages: int


class AdminSettingListResponse(PaginatedResponse):
    """Paginated list of admin settings"""
    items: list[AdminSettingResponse]


class AdminAuditLogListResponse(PaginatedResponse):
    """Paginated list of audit logs"""
    items: list[AdminAuditLogResponse]


class ApplicationLogListResponse(PaginatedResponse):
    """Paginated list of application logs"""
    items: list[ApplicationLogResponse]


class SecurityEventListResponse(PaginatedResponse):
    """Paginated list of security events"""
    items: list[SecurityEventResponse]
