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
        allowed_categories = ['email', 'ai', 'processing', 'application', 'system', 'api_keys', 'openai', 'features']
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


# Configuration Status Schemas
class ConfigIssueItem(BaseModel):
    """Schema for a configuration issue"""
    key: str
    category: str
    issues: Optional[list[str]] = None
    required: Optional[bool] = None
    description: Optional[str] = None
    current_value: Optional[Any] = None
    env_value: Optional[Any] = None


class ConfigStatusResponse(BaseModel):
    """Schema for configuration status response"""
    total_expected: int = Field(..., description="Total number of expected settings")
    total_found: int = Field(..., description="Total number of settings found in database")
    valid_count: int = Field(..., description="Number of valid settings")
    incomplete_count: int = Field(..., description="Number of incomplete settings")
    missing_count: int = Field(..., description="Number of missing settings")
    extra_count: int = Field(..., description="Number of extra settings")

    missing: list[ConfigIssueItem] = Field(default_factory=list, description="Missing required settings")
    incomplete: list[ConfigIssueItem] = Field(default_factory=list, description="Incomplete settings")
    valid: list[dict] = Field(default_factory=list, description="Valid settings")
    extra: list[dict] = Field(default_factory=list, description="Extra settings not in config_helper")

    is_healthy: bool = Field(..., description="Whether all configuration is properly set")
    recommendations: list[str] = Field(default_factory=list, description="Recommendations for fixing issues")


class SecurityEventListResponse(PaginatedResponse):
    """Paginated list of security events"""
    items: list[SecurityEventResponse]


# System Announcement Schemas
class SystemAnnouncementCreate(BaseModel):
    """Schema for creating a system announcement"""
    title: str = Field(..., min_length=1, max_length=255, description="Announcement title")
    message: str = Field(..., min_length=1, description="Announcement message")
    priority: str = Field(default="medium", description="Priority: 'low', 'medium', 'high'")
    target_all_users: bool = Field(default=True, description="Send to all users")
    target_user_ids: Optional[list[UUID]] = Field(None, description="Specific user IDs to target (if not all users)")

    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v: str) -> str:
        """Validate priority level"""
        allowed_priorities = ['low', 'medium', 'high']
        if v not in allowed_priorities:
            raise ValueError(f"priority must be one of {allowed_priorities}")
        return v


class SystemAnnouncementResponse(BaseModel):
    """Schema for system announcement response"""
    success: bool
    announcement_id: UUID
    notifications_created: int
    emails_sent: int
    message: str


# User Management Schemas
class UserBase(BaseModel):
    """Base schema for user"""
    email: str
    is_active: bool
    is_admin: bool
    email_verified: bool


class UserResponse(UserBase):
    """Schema for user response"""
    id: str
    created_at: str
    updated_at: str


class UserDetailResponse(UserResponse):
    """Schema for detailed user response"""
    settings: dict
    subscription_count: int
    mailbox_count: int


class UserUpdateRequest(BaseModel):
    """Schema for updating user"""
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


class UserListResponse(PaginatedResponse):
    """Paginated list of users"""
    users: list[UserResponse]


class UserStatsResponse(BaseModel):
    """User statistics"""
    total_users: int
    active_users: int
    inactive_users: int
    admin_users: int
    new_users_30d: int


# Log Management Schemas
class LogEntryResponse(BaseModel):
    """Schema for log entry"""
    id: str
    timestamp: str
    level: str
    module: str
    message: str
    source: str


class LogListResponse(PaginatedResponse):
    """Paginated list of logs"""
    logs: list[LogEntryResponse]


# IP Whitelist Schemas
class IPWhitelistCreate(BaseModel):
    """Schema for creating an IP whitelist entry"""
    ip_address: str = Field(..., description="IP address to whitelist (IPv4 or IPv6)")
    description: Optional[str] = Field(None, max_length=255, description="Description of why this IP is whitelisted")


class IPWhitelistUpdate(BaseModel):
    """Schema for updating an IP whitelist entry"""
    description: Optional[str] = Field(None, max_length=255, description="Update description")


class IPWhitelistResponse(BaseModel):
    """Schema for IP whitelist response"""
    ip_address: str
    description: Optional[str]
    added_by_user_id: str
    added_at: datetime
    last_seen: Optional[datetime]
    access_count: int

    model_config = ConfigDict(from_attributes=True)


class IPWhitelistListResponse(PaginatedResponse):
    """Paginated list of IP whitelist entries"""
    items: list[IPWhitelistResponse]
