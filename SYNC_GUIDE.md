# Email Sync Guide

Complete guide for syncing emails with custom date ranges and OpenAI rate limiting.

## Quick Start

### Sync Last 365 Days (1 Year)

```bash
bash scripts/sync_custom_period.sh
```

Follow the interactive prompts:
1. Enter your mailbox ID
2. Choose option **5** for last 365 days
3. Optionally configure rate limiting
4. Confirm and start

## Custom Date Ranges

The system supports flexible date range specifications:

### Standard Periods

- **7 days**: `7days` - Last week of emails
- **30 days**: `30days` - Last month (default)
- **90 days**: `90days` - Last 3 months
- **180 days**: `180days` - Last 6 months
- **365 days**: `365days` - Last full year

### Custom Periods

You can specify any number of days:
- `14days` - 2 weeks
- `60days` - 2 months
- `730days` - 2 years

### Using Different Formats

The system also supports month and year formats:
- `1month`, `3months`, `6months`, `12months`
- `1year`, `2years`

## OpenAI Rate Limiting

### Why Rate Limiting Matters

OpenAI has API rate limits based on your tier:
- **Free tier**: ~3 requests per minute (very restrictive)
- **Tier 1**: ~60 requests per minute
- **Tier 2**: ~3,500 requests per minute
- **Higher tiers**: Even higher limits

**Without rate limiting**, large email syncs will fail with rate limit errors.

### Default Rate Limiting

Current defaults (configured in `.env`):
```
OPENAI_REQUEST_DELAY_SECONDS=1.0
OPENAI_MAX_REQUESTS_PER_MINUTE=60
```

This means:
- 1 second delay between each email processed
- Maximum 60 requests per minute
- Safe for Tier 1 and above

### Adjusting Rate Limits

Edit your `.env` file to customize:

```bash
# For free tier or cautious usage (slower but safer)
OPENAI_REQUEST_DELAY_SECONDS=2.0
OPENAI_MAX_REQUESTS_PER_MINUTE=3

# For Tier 2+ (faster processing)
OPENAI_REQUEST_DELAY_SECONDS=0.5
OPENAI_MAX_REQUESTS_PER_MINUTE=100

# For very high tiers (maximum speed)
OPENAI_REQUEST_DELAY_SECONDS=0.1
OPENAI_MAX_REQUESTS_PER_MINUTE=500
```

**After changing `.env`**:
```bash
docker-compose -f docker-compose.dev.yml restart backend celery
```

### Time Estimates

Estimated sync times with default rate limiting (1 second delay):

| Email Volume | Time Required | OpenAI Requests |
|--------------|---------------|-----------------|
| 100 emails | ~2-3 minutes | ~100-200 |
| 500 emails | ~10-15 minutes | ~500-1000 |
| 1000 emails | ~20-30 minutes | ~1000-2000 |
| 5000 emails | ~2-3 hours | ~5000-10000 |

**Note**: Each email makes 1-2 OpenAI API calls:
1. Classification (all emails)
2. Extraction (only subscription emails)

## Sync Methods

### Method 1: Interactive Script (Recommended)

```bash
bash scripts/sync_custom_period.sh
```

**Advantages**:
- User-friendly prompts
- Period selection menu
- Optional rate limit configuration
- Confirmation before starting

### Method 2: Direct API Call

```bash
# Get your authentication token
TOKEN="your-access-token"
MAILBOX_ID="your-mailbox-id"

# Sync last 365 days
curl -X POST "http://localhost:8000/api/mailboxes/${MAILBOX_ID}/sync" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"force_full_sync": false, "date_filter": "365days"}'
```

### Method 3: Via Web UI (Future Enhancement)

Currently in development - will allow selecting custom date ranges from the UI.

## Monitoring Sync Progress

### Check Celery Logs

```bash
docker logs -f subscriptions_celery
```

Look for:
- `Starting email sync for mailbox...`
- `Fetched X emails from mailbox...`
- `Subscription email detected: ...`
- `Rate limiting: waiting 1.0s before next email...`

### Check Sync Status in Database

```bash
docker exec -i subscriptions_db psql -U postgres -d subscription_tracker -c "
SELECT
  id,
  email_address,
  last_sync_at,
  last_sync_status,
  last_sync_emails_processed,
  last_sync_subscriptions_found
FROM mailboxes;
"
```

### Web UI Status

Navigate to the Mailboxes page to see:
- Last sync time
- Sync status (in_progress, success, failed)
- Emails processed
- Subscriptions found

## Troubleshooting

### Rate Limit Errors

**Error**: `Rate limit exceeded` or `429 Too Many Requests`

**Solutions**:
1. Increase `OPENAI_REQUEST_DELAY_SECONDS` in `.env`
2. Reduce `OPENAI_MAX_REQUESTS_PER_MINUTE`
3. Upgrade your OpenAI tier
4. Process emails in smaller batches

### Sync Timeout

**Error**: Sync never completes or gets stuck

**Solutions**:
1. Check Celery logs for errors
2. Reduce batch size: `DEFAULT_BATCH_SIZE=50`
3. Sync smaller date ranges incrementally

### Authentication Failed

**Error**: `Authentication failed` during sync

**Solutions**:
1. Verify mailbox credentials in web UI
2. Check JMAP server availability
3. Re-authenticate mailbox

### No Subscriptions Found

**Issue**: Sync completes but finds no subscriptions

**Possible Causes**:
1. Emails in the period don't contain subscriptions
2. Classification confidence too low
3. Email content not accessible

**Solutions**:
1. Check AI Sandbox to review uncertain emails
2. Manually verify some emails are subscription-related
3. Adjust confidence thresholds in `.env`

## Best Practices

### Initial Setup

1. **Start small**: Sync 7-30 days first to verify everything works
2. **Monitor closely**: Watch Celery logs during first sync
3. **Verify results**: Check found subscriptions match expectations
4. **Adjust settings**: Fine-tune rate limits based on results

### Large Syncs (365 days)

1. **Run overnight**: Large syncs can take hours
2. **Monitor OpenAI costs**: Each email = 1-2 API calls
3. **Use batch processing**: Consider syncing in chunks (90 days at a time)
4. **Avoid duplicates**: The system handles duplicate emails automatically

### Rate Limit Strategy

| OpenAI Tier | Recommended Delay | Max Req/Min |
|-------------|-------------------|-------------|
| Free | 2.0 seconds | 3 |
| Tier 1 | 1.0 seconds | 60 |
| Tier 2 | 0.5 seconds | 100 |
| Tier 3+ | 0.2 seconds | 300 |

### Cost Management

OpenAI API costs for email processing:
- **GPT-4o mini** (default): ~$0.15 per 1000 emails
- **GPT-4o**: ~$2.50 per 1000 emails

For 365 days with 5000 emails:
- **Estimated cost**: $0.75 - $12.50 depending on model

## Configuration Reference

### Environment Variables

```bash
# Sync period
DEFAULT_SYNC_PERIOD_DAYS=30  # 7, 30, 90, 180, or 365

# Rate limiting
OPENAI_REQUEST_DELAY_SECONDS=1.0  # 0.1 to 5.0
OPENAI_MAX_REQUESTS_PER_MINUTE=60  # 3 to 500+

# Processing
DEFAULT_BATCH_SIZE=100  # 50, 100, 200, or 500
```

### Date Filter Formats

Supported in API calls and scripts:
```json
{
  "date_filter": "365days"   // Most flexible
  "date_filter": "1year"     // Same as 365days
  "date_filter": "12months"  // Same as 365days
}
```

## Advanced Usage

### Incremental Sync Strategy

For very large mailboxes, sync incrementally:

```bash
# Sync oldest period first
bash scripts/sync_custom_period.sh  # Choose 365days

# Wait for completion, then sync recent changes
bash scripts/sync_custom_period.sh  # Choose 7days
```

### Parallel Mailbox Sync

Sync multiple mailboxes in parallel:

```bash
# Terminal 1
bash scripts/sync_custom_period.sh
# Enter mailbox_id_1, choose 365days

# Terminal 2
bash scripts/sync_custom_period.sh
# Enter mailbox_id_2, choose 365days
```

**Note**: Monitor OpenAI rate limits carefully when running parallel syncs.

### Custom Batch Processing

Process specific date ranges programmatically:

```python
from app.tasks.email_sync import sync_mailbox_emails

# Sync Q1 2024
result = sync_mailbox_emails(
    mailbox_id="your-mailbox-id",
    force_full_sync=False,
    date_filter="90days"  # Adjust to cover desired period
)
```

## FAQ

**Q: Can I sync more than 365 days?**
A: Yes! Use `730days` for 2 years, or any custom number.

**Q: Will syncing again create duplicates?**
A: No. The system uses Message-ID to detect and skip duplicate emails.

**Q: How do I know my OpenAI tier?**
A: Check your OpenAI account at https://platform.openai.com/account/limits

**Q: Can I pause a running sync?**
A: Not easily. Best to let it complete or restart Celery worker.

**Q: Why is my sync slow?**
A: Rate limiting adds deliberate delays to respect OpenAI limits. Adjust `OPENAI_REQUEST_DELAY_SECONDS` for your tier.

**Q: How do I sync all my historical emails?**
A: Use a very large number like `3650days` (10 years) or `7300days` (20 years).

## Support

For issues or questions:
1. Check Celery logs: `docker logs -f subscriptions_celery`
2. Review this guide
3. Check OpenAI usage dashboard for rate limit status
4. Verify `.env` configuration matches your OpenAI tier
