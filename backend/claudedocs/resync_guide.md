# Re-syncing OVH Emails with Service References

## Quick Options

### Option 1: Safe Re-sync Script (Recommended) ⭐

Re-process emails without deleting anything:

```bash
# 1. Dry-run first (see what would change)
docker exec subscriptions_backend python scripts/resync_ovh_emails.py --provider OVH

# 2. If results look good, apply changes
docker exec subscriptions_backend python scripts/resync_ovh_emails.py --provider OVH --apply
```

**Benefits**:
- Safe - doesn't delete data
- Shows preview before applying
- Updates existing records with service references
- Can target specific providers

### Option 2: Reset Sync State

Mark emails as unprocessed so they'll be re-synced:

```bash
# Connect to database
docker exec -it subscriptions_postgres psql -U subscriptions -d subscriptions

# Reset OVH emails
UPDATE emails
SET sync_status = 'pending',
    processed_at = NULL
WHERE sender LIKE '%ovh%';

# Exit database
\q

# Trigger sync
docker exec subscriptions_backend python -c "from app.tasks.email_sync import sync_emails_task; sync_emails_task.delay()"
```

**Warning**: This will re-link emails to subscriptions, which might create duplicates if matching logic has issues.

### Option 3: Fresh Start (Nuclear Option)

Delete and re-fetch everything from OVH:

```bash
# 1. Connect to database
docker exec -it subscriptions_postgres psql -U subscriptions -d subscriptions

# 2. Delete OVH data
DELETE FROM emails WHERE sender LIKE '%ovh%';
DELETE FROM subscriptions WHERE provider = 'OVH';

# 3. Exit
\q

# 4. Re-fetch last 30 days
docker exec subscriptions_backend python -c "
from app.tasks.email_sync import fetch_new_emails_task
fetch_new_emails_task.delay(days_back=30)
"

# 5. Monitor logs
docker logs -f subscriptions_celery
```

**Warning**: Deletes all OVH subscriptions and emails. Only use if you want to start fresh.

## Recommended Workflow

### Step 1: Test with Dry-Run

```bash
docker exec subscriptions_backend python scripts/resync_ovh_emails.py --provider OVH
```

Look for output like:
```
Processing email: Renouvellement de votre service FR73880615
Extraction results:
  Custom label: VPS - FR73880615
  Service references: {'service_code': 'FR73880615', 'domain': 'example.com'}
  Service type: VPS
  [DRY RUN] Would update with service references
```

### Step 2: Apply Changes

If dry-run looks good:

```bash
docker exec subscriptions_backend python scripts/resync_ovh_emails.py --provider OVH --apply
```

### Step 3: Verify Results

```bash
# Check database
docker exec -it subscriptions_postgres psql -U subscriptions -d subscriptions

# See subscriptions with service references
SELECT
    id,
    provider,
    custom_label,
    extraction_metadata->'service_references' as references
FROM subscriptions
WHERE provider = 'OVH';

\q
```

### Step 4: Test Future Emails

Send a new OVH email or wait for next renewal email to verify:
1. Email gets extracted with service references
2. Matches to correct existing subscription
3. Check logs: `docker logs subscriptions_celery | grep "service_references"`

## Troubleshooting

### Issue: No service references extracted

**Check**:
1. Email actually contains service code (FR\d{8})
2. Pattern is correct in `provider_patterns.py`
3. Logs for extraction: `docker logs subscriptions_celery | grep "No service references"`

**Fix**: Verify email content or adjust regex pattern

### Issue: Duplicate subscriptions created

**Cause**: Matching logic didn't find existing subscription

**Fix**:
```bash
# Merge duplicates manually
docker exec -it subscriptions_postgres psql -U subscriptions -d subscriptions

-- Find duplicates
SELECT id, custom_label, created_at
FROM subscriptions
WHERE provider = 'OVH'
ORDER BY custom_label, created_at;

-- Update emails to point to correct subscription
UPDATE emails
SET subscription_id = <correct_id>
WHERE subscription_id = <duplicate_id>;

-- Delete duplicate
DELETE FROM subscriptions WHERE id = <duplicate_id>;
```

### Issue: Script fails with import error

**Fix**: Ensure you're running from Docker:
```bash
docker exec subscriptions_backend python scripts/resync_ovh_emails.py --provider OVH
```

Not: `python scripts/resync_ovh_emails.py` (outside Docker)

## Script Options

```bash
# Re-sync different provider
docker exec subscriptions_backend python scripts/resync_ovh_emails.py --provider AWS --apply

# Dry-run for multiple providers
docker exec subscriptions_backend python scripts/resync_ovh_emails.py --provider "Google Cloud"

# Check help
docker exec subscriptions_backend python scripts/resync_ovh_emails.py --help
```

## What Gets Updated

The re-sync script updates:

1. **Email.extraction_metadata**: Adds service references
2. **Subscription.extraction_metadata**: Merges service references
3. **Subscription.custom_label**: Updates if better label found

It preserves:
- All other subscription data (amount, billing cycle, etc.)
- Email history
- Payment history
- User associations

## Best Practice

1. **Always dry-run first** to preview changes
2. **Backup database** before major changes:
   ```bash
   docker exec subscriptions_postgres pg_dump -U subscriptions subscriptions > backup.sql
   ```
3. **Monitor logs** during re-sync
4. **Verify results** with database queries
5. **Test matching** with a new email before trusting it

## After Re-sync

Check that service reference matching is working:

```bash
# Monitor next email sync
docker logs -f subscriptions_celery

# Look for:
# "Found matching service reference: service_code=FR73880615"
# "Found service reference match for OVH: {'service_code': 'FR73880615'}"
```
