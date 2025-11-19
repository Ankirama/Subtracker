# Admin Configuration Management Guide

## Overview

The admin configuration system allows runtime management of application settings through the admin panel. Settings can be managed via database overrides instead of requiring .env changes and application restarts.

## Architecture

### Configuration Priority System

```
1. Admin Settings (database) → Runtime configurable
2. Environment Variables (.env) → Deployment specific
3. Default Values (code) → Fallback defaults
```

### Settings Categories

#### **email** - SendGrid Configuration
- `sendgrid.api_key` (secret, required)
- `sendgrid.from_email` (required)
- `sendgrid.from_name` (required)

#### **ai** - OpenAI Configuration
- `openai.api_key` (secret, required)
- `openai.assistant_id` (optional)
- `openai.request_delay_seconds` (required)
- `openai.max_requests_per_minute` (required)

#### **processing** - Email Processing Configuration
- `email.default_batch_size` (required)
- `email.confidence_auto_accept` (required)
- `email.confidence_review_min` (required)
- `email.default_sync_period_days` (required)

#### **application** - Application Settings
- `frontend.url` (required)

## Configuration Monitoring

### CLI Tool

Check configuration status from command line:

```bash
# Check all settings
docker exec subscriptions_backend python -m scripts.check_admin_config

# Example output:
# ======================================================================
# 📊 ADMIN CONFIGURATION STATUS
# ======================================================================
#
# 📈 Overview:
#    Total Expected Settings: 12
#    Total Found in Database: 12
#    ✅ Valid:     12
#    ⚠️  Incomplete: 0
#    ❌ Missing:    0
```

**Exit Codes:**
- `0` - All settings properly configured
- `1` - Missing or incomplete settings found
- `2` - Error occurred during check

### API Endpoint

Frontend can check configuration status:

```http
GET /admin/config/status
Authorization: Bearer {admin_token}
```

**Response:**
```json
{
  "total_expected": 12,
  "total_found": 12,
  "valid_count": 12,
  "incomplete_count": 0,
  "missing_count": 0,
  "extra_count": 0,
  "is_healthy": true,
  "valid": [
    {"key": "sendgrid.api_key", "category": "email"},
    {"key": "openai.api_key", "category": "ai"},
    ...
  ],
  "missing": [],
  "incomplete": [],
  "extra": [],
  "recommendations": []
}
```

## Setup & Management

### Initial Setup

1. **Seed Database with Current Configuration**
   ```bash
   docker exec subscriptions_backend python -m scripts.seed_admin_settings
   ```

2. **Verify Settings**
   ```bash
   docker exec subscriptions_backend python -m scripts.check_admin_config
   ```

### Updating Settings

#### Via API (Recommended)

```http
PUT /admin/config/{key}
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "value": "new_value",
  "description": "Updated via admin panel"
}
```

#### Via Seed Script (Batch Updates)

```bash
# Update all settings from current .env
docker exec subscriptions_backend python -m scripts.seed_admin_settings --overwrite
```

## Frontend Integration

### Display Configuration Status

```typescript
interface ConfigStatus {
  total_expected: number;
  total_found: number;
  valid_count: number;
  incomplete_count: number;
  missing_count: number;
  is_healthy: boolean;
  missing: ConfigIssueItem[];
  incomplete: ConfigIssueItem[];
  valid: {key: string, category: string}[];
  recommendations: string[];
}

// Fetch status
const response = await fetch('/admin/config/status', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const status: ConfigStatus = await response.json();

// Display health indicator
if (status.is_healthy) {
  // Show green status: "All settings configured ✅"
} else {
  // Show warning: "⚠️ {status.missing_count} missing, {status.incomplete_count} incomplete"
  // Display recommendations
}
```

### Configuration Dashboard

```typescript
// Group settings by category
const settingsByCategory = {
  email: ['sendgrid.api_key', 'sendgrid.from_email', 'sendgrid.from_name'],
  ai: ['openai.api_key', 'openai.assistant_id', ...],
  processing: ['email.default_batch_size', ...],
  application: ['frontend.url']
};

// Render categorized settings with:
// - Green checkmark for valid settings
// - Yellow warning for incomplete
// - Red alert for missing
// - Secret fields masked with password input
```

## Testing

### Test Configuration Flow

1. **Check Current Status**
   ```bash
   docker exec subscriptions_backend python -m scripts.check_admin_config
   ```

2. **Update via API**
   ```bash
   curl -X PUT http://localhost:8000/admin/config/frontend.url \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"value":"http://localhost:3000"}'
   ```

3. **Verify Update**
   ```bash
   curl http://localhost:8000/admin/config/frontend.url \
     -H "Authorization: Bearer $TOKEN"
   ```

4. **Test Priority System**
   - Update setting in database
   - Verify service uses database value over .env
   - Check application logs for "Using admin setting for..." messages

## Troubleshooting

### Missing Settings

**Symptoms:** `/admin/config/status` shows missing settings

**Solutions:**
```bash
# Run seed script to create missing settings
docker exec subscriptions_backend python -m scripts.seed_admin_settings
```

### Incomplete Settings

**Symptoms:** Settings exist but have placeholder values or wrong types

**Solutions:**
1. Update via Admin Panel UI
2. Or re-run seed with --overwrite:
   ```bash
   docker exec subscriptions_backend python -m scripts.seed_admin_settings --overwrite
   ```

### Settings Not Taking Effect

**Symptoms:** Updated setting but application still uses old value

**Checks:**
1. Verify setting is in database: `GET /admin/config/{key}`
2. Check if service is using config_helper (should log "Using admin setting for...")
3. For Celery tasks, restart worker: `docker restart subscriptions_celery`

## Security Considerations

### Secret Management

- **Secret settings** (API keys) are encrypted in database using Fernet encryption
- Encryption key stored in `.env` as `ENCRYPTION_KEY`
- Never expose decrypted secrets in logs or frontend
- API returns masked values for secrets by default
- Use `decrypt=true` query parameter only when necessary

### Access Control

- All admin config endpoints require admin role
- Audit logs track all configuration changes
- Include user ID, timestamp, and old/new values in audit trail

## Best Practices

1. **Initial Setup**: Always run seed script after deployment
2. **Regular Checks**: Monitor `/admin/config/status` in admin dashboard
3. **Audit Trail**: Review admin audit logs for unauthorized changes
4. **Backup**: Include `admin_settings` table in database backups
5. **Documentation**: Document any new settings added to config_helper
6. **Testing**: Test config changes in staging before production
7. **Rollback**: Keep previous values in audit logs for easy rollback

## Adding New Settings

When adding a new admin-configurable setting:

1. **Update config_helper.py**: Add mapping to `env_mapping` dictionary
2. **Update seed script**: Add to `settings_to_seed` array in `seed_admin_settings.py`
3. **Update check script**: Add to `EXPECTED_SETTINGS` in `check_admin_config.py`
4. **Update API endpoint**: Add to `EXPECTED_SETTINGS` in `config.py`
5. **Update services**: Replace `settings.SETTING_NAME` with `get_config_value('setting.key', settings.SETTING_NAME, db)`
6. **Run seed**: Execute `python -m scripts.seed_admin_settings`
7. **Verify**: Check `/admin/config/status` shows new setting as valid
