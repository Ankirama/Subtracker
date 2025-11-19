# Admin Panel Architecture

## Overview
The admin panel provides runtime configuration management, user management, system monitoring, and security features for the subscription tracker application.

## Core Components

### 1. Configuration Management
**Location**: `/api/admin/config`

**Features**:
- Runtime configuration changes without restart
- Encrypted storage for API keys (Fernet)
- Configuration health monitoring
- Database-backed settings with .env fallback

**Key Endpoints**:
- `GET /admin/config` - List all settings (paginated)
- `GET /admin/config/{key}` - Get specific setting
- `POST /admin/config` - Create new setting
- `PUT /admin/config/{key}` - Update setting
- `DELETE /admin/config/{key}` - Delete setting
- `GET /admin/config/status` - Configuration health status

**Configuration Categories**:
- **email**: SendGrid configuration
- **ai**: OpenAI/AI processing configuration
- **processing**: Email processing thresholds and defaults
- **application**: Frontend URL and app-level settings
- **system**: Legacy/miscellaneous settings

**Security**:
- Fernet symmetric encryption for secrets
- Admin role required for all operations
- Audit logging for all changes
- Secrets masked in UI by default

### 2. User Management
**Location**: `/api/admin/users`

**Capabilities**:
- View all users with filtering
- Activate/deactivate user accounts
- Promote/demote admin privileges
- View user statistics
- Access user details (subscription count, mailbox count)

### 3. Security Events
**Location**: `/api/admin/security`

**Features**:
- Security event logging and monitoring
- Event types: failed_login, brute_force, suspicious_activity
- Severity levels: low, medium, high, critical
- Resolution tracking
- IP whitelist management

### 4. System Logs
**Location**: `/api/admin/logs`

**Features**:
- Application log aggregation
- Log level filtering (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Log source tracking
- Search and pagination

### 5. System Announcements
**Location**: `/api/admin/announcements`

**Features**:
- Broadcast messages to all users
- Targeted announcements to specific users
- Priority levels (low, medium, high)
- Email + in-app notification delivery

## Architecture Patterns

### Configuration Priority System
```
1. Admin Settings (database) → Runtime configurable
2. Environment Variables (.env) → Deployment specific  
3. Default Values (code) → Fallback defaults
```

**Implementation**: `config_helper.py`
```python
def get_config_value(key: str, default, db: Session = None):
    # 1. Check database first
    if db:
        admin_setting = query_admin_setting(key)
        if admin_setting:
            return decrypt_if_secret(admin_setting)
    
    # 2. Fall back to env vars
    env_value = ENV_MAPPING.get(key)
    if env_value:
        return env_value
    
    # 3. Return default
    return default
```

### Encryption Service
**Location**: `app/utils/encryption.py`

**Algorithm**: Fernet (AES-128 in CBC mode with HMAC)

**Key Management**:
- Master key: `ENCRYPTION_KEY` in .env
- Never stored in database
- Should be rotated periodically
- Use key management service in production (AWS KMS, Vault)

**Usage**:
```python
from app.utils.encryption import encryption_service

# Encrypt
encrypted = encryption_service.encrypt("secret_value")

# Decrypt
decrypted = encryption_service.decrypt(encrypted)
```

### Audit Logging
**Location**: `app/models/admin.py` - `AdminAuditLog`

**Captured Information**:
- User ID (who performed action)
- Action type (create_setting, update_user, etc.)
- Resource type and ID (what was affected)
- Details (metadata about the change)
- IP address and user agent
- Severity level
- Timestamp

**Security Note**: Never log actual secret values, only metadata

### Frontend Integration
**Component**: `AdminConfigPage.tsx`

**Features**:
- Configuration health dashboard
- Missing/incomplete settings alerts
- CRUD operations for settings
- Secret value masking/revealing
- Category filtering and search

**Status Display Logic**:
```typescript
if (configStatus.is_healthy) {
  // Green success banner
} else {
  // Warning alert with issue counts
  // Red box for missing settings
  // Orange box for incomplete settings
  // Recommendations for fixes
}
```

## Security Considerations

### Access Control
- All admin endpoints require `is_admin=true` user role
- Implemented in `security/dependencies.py`
- JWT-based authentication with role checking

### Encryption at Rest
- All secrets encrypted in database using Fernet
- Encryption key stored securely in environment
- Keys never exposed in API responses by default

### Audit Trail
- All admin actions logged in `admin_audit_logs` table
- Includes user, timestamp, action, and affected resources
- Enables security forensics and compliance

### IP Whitelisting
- Optional IP-based access control for admin endpoints
- Managed through `/api/admin/security/ip-whitelist`
- Tracks last access and usage count

## Tools and Scripts

### Database Seeding
**Script**: `scripts/seed_admin_settings.py`

**Purpose**: Populate database with initial configuration from .env

**Usage**:
```bash
docker exec subscriptions_backend python -m scripts.seed_admin_settings
docker exec subscriptions_backend python -m scripts.seed_admin_settings --overwrite
```

### Configuration Health Check
**Script**: `scripts/check_admin_config.py`

**Purpose**: Validate configuration completeness and correctness

**Usage**:
```bash
docker exec subscriptions_backend python -m scripts.check_admin_config
echo $?  # 0=healthy, 1=issues, 2=error
```

## Best Practices

### For Developers
1. Use `get_config_value()` for any setting that should be admin-configurable
2. Add new settings to all 4 locations (config_helper, seed script, check script, API schema)
3. Mark sensitive values with `is_secret=True`
4. Never log decrypted secret values
5. Always provide fallback defaults

### For Admins
1. Run seed script after initial deployment
2. Monitor configuration status regularly
3. Review audit logs for unauthorized changes
4. Keep ENCRYPTION_KEY secure and backed up
5. Rotate encryption key periodically
6. Use strong API keys and credentials

### For Operations
1. Include `admin_settings` table in database backups
2. Secure `.env` file with proper permissions
3. Use key management service in production
4. Monitor security events for anomalies
5. Test configuration changes in staging first

## Migration Strategy

### Adding New Configurable Setting
1. Update `config_helper.py` env_mapping
2. Update `seed_admin_settings.py` settings array
3. Update `check_admin_config.py` EXPECTED_SETTINGS
4. Update `api/admin/config.py` EXPECTED_SETTINGS  
5. Update service code to use `get_config_value()`
6. Run seed script in all environments
7. Verify with check script

### Removing Configuration Setting
1. Update all EXPECTED_SETTINGS lists
2. Update service code to remove `get_config_value()` calls
3. Manually delete from database if needed
4. Update documentation

### Encryption Key Rotation
1. Generate new encryption key
2. Create migration script to re-encrypt all secrets with new key
3. Update ENCRYPTION_KEY in .env
4. Run migration script
5. Verify all services can decrypt secrets
6. Backup old key for rollback period

## Future Enhancements

### Planned Features
- Configuration versioning and rollback
- Configuration import/export for environment promotion
- Validation rules for settings (format, range checks)
- Configuration templates for common setups
- Multi-environment configuration management
- Configuration change approval workflow
- Real-time configuration updates via WebSocket

### Performance Optimizations
- Cache frequently accessed settings in memory
- Implement configuration change notifications
- Optimize database queries with indexes
- Add read replicas for configuration reads
