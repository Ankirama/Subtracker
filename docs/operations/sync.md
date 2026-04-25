# Email Sync

> Complete guide to email sync: backend processing, custom date ranges,
> rate limiting, and the frontend UI with progress tracking.

---

## Backend Sync

Complete guide for syncing emails with custom date ranges and OpenAI rate limiting
via CLI scripts or direct API calls.

### Quick Start

#### Sync Last 365 Days (1 Year)

```bash
bash scripts/sync_custom_period.sh
```

Follow the interactive prompts:
1. Enter your mailbox ID
2. Choose option **5** for last 365 days
3. Optionally configure rate limiting
4. Confirm and start

### Custom Date Ranges

The system supports flexible date range specifications.

#### Standard Periods

- **7 days**: `7days` - Last week of emails
- **30 days**: `30days` - Last month (default)
- **90 days**: `90days` - Last 3 months
- **180 days**: `180days` - Last 6 months
- **365 days**: `365days` - Last full year

#### Custom Periods

You can specify any number of days:
- `14days` - 2 weeks
- `60days` - 2 months
- `730days` - 2 years

#### Using Month and Year Formats

The system also supports month and year formats:
- `1month`, `3months`, `6months`, `12months`
- `1year`, `2years`

### OpenAI Rate Limiting

#### Why Rate Limiting Matters

OpenAI has API rate limits based on your tier:
- **Free tier**: ~3 requests per minute (very restrictive)
- **Tier 1**: ~60 requests per minute
- **Tier 2**: ~3,500 requests per minute
- **Higher tiers**: Even higher limits

**Without rate limiting**, large email syncs will fail with rate limit errors.

#### Default Rate Limiting

Current defaults (configured in `.env`):
```
OPENAI_REQUEST_DELAY_SECONDS=1.0
OPENAI_MAX_REQUESTS_PER_MINUTE=60
```

This means:
- 1 second delay between each email processed
- Maximum 60 requests per minute
- Safe for Tier 1 and above

#### Adjusting Rate Limits

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

#### Time Estimates

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

### Sync Methods

#### Method 1: Interactive Script (Recommended)

```bash
bash scripts/sync_custom_period.sh
```

**Advantages**:
- User-friendly prompts
- Period selection menu
- Optional rate limit configuration
- Confirmation before starting

#### Method 2: Direct API Call

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

#### Method 3: Via Web UI

See the [Frontend Sync UI](#frontend-sync-ui) section below for UI-based syncing
with real-time progress tracking.

### Monitoring Sync Progress

#### Check Celery Logs

```bash
docker logs -f subscriptions_celery
```

Look for:
- `Starting email sync for mailbox...`
- `Fetched X emails from mailbox...`
- `Subscription email detected: ...`
- `Rate limiting: waiting 1.0s before next email...`

#### Check Sync Status in Database

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

#### Web UI Status

Navigate to the Mailboxes page to see:
- Last sync time
- Sync status (in_progress, success, failed)
- Emails processed
- Subscriptions found

### Troubleshooting

#### Rate Limit Errors

**Error**: `Rate limit exceeded` or `429 Too Many Requests`

**Solutions**:
1. Increase `OPENAI_REQUEST_DELAY_SECONDS` in `.env`
2. Reduce `OPENAI_MAX_REQUESTS_PER_MINUTE`
3. Upgrade your OpenAI tier
4. Process emails in smaller batches

#### Sync Timeout

**Error**: Sync never completes or gets stuck

**Solutions**:
1. Check Celery logs for errors
2. Reduce batch size: `DEFAULT_BATCH_SIZE=50`
3. Sync smaller date ranges incrementally

#### Authentication Failed

**Error**: `Authentication failed` during sync

**Solutions**:
1. Verify mailbox credentials in web UI
2. Check JMAP server availability
3. Re-authenticate mailbox

#### No Subscriptions Found

**Issue**: Sync completes but finds no subscriptions

**Possible Causes**:
1. Emails in the period don't contain subscriptions
2. Classification confidence too low
3. Email content not accessible

**Solutions**:
1. Check AI Sandbox to review uncertain emails
2. Manually verify some emails are subscription-related
3. Adjust confidence thresholds in `.env`

### Best Practices

#### Initial Setup

1. **Start small**: Sync 7-30 days first to verify everything works
2. **Monitor closely**: Watch Celery logs during first sync
3. **Verify results**: Check found subscriptions match expectations
4. **Adjust settings**: Fine-tune rate limits based on results

#### Large Syncs (365 days)

1. **Run overnight**: Large syncs can take hours
2. **Monitor OpenAI costs**: Each email = 1-2 API calls
3. **Use batch processing**: Consider syncing in chunks (90 days at a time)
4. **Avoid duplicates**: The system handles duplicate emails automatically

#### Rate Limit Strategy

| OpenAI Tier | Recommended Delay | Max Req/Min |
|-------------|-------------------|-------------|
| Free | 2.0 seconds | 3 |
| Tier 1 | 1.0 seconds | 60 |
| Tier 2 | 0.5 seconds | 100 |
| Tier 3+ | 0.2 seconds | 300 |

#### Cost Management

OpenAI API costs for email processing:
- **GPT-4o mini** (default): ~$0.15 per 1000 emails
- **GPT-4o**: ~$2.50 per 1000 emails

For 365 days with 5000 emails:
- **Estimated cost**: $0.75 - $12.50 depending on model

### Configuration Reference

#### Environment Variables

```bash
# Sync period
DEFAULT_SYNC_PERIOD_DAYS=30  # 7, 30, 90, 180, or 365

# Rate limiting
OPENAI_REQUEST_DELAY_SECONDS=1.0  # 0.1 to 5.0
OPENAI_MAX_REQUESTS_PER_MINUTE=60  # 3 to 500+

# Processing
DEFAULT_BATCH_SIZE=100  # 50, 100, 200, or 500
```

#### Date Filter Formats

Supported in API calls and scripts:
```json
{
  "date_filter": "365days",
  "date_filter": "1year",
  "date_filter": "12months"
}
```

### Advanced Usage

#### Incremental Sync Strategy

For very large mailboxes, sync incrementally:

```bash
# Sync oldest period first
bash scripts/sync_custom_period.sh  # Choose 365days

# Wait for completion, then sync recent changes
bash scripts/sync_custom_period.sh  # Choose 7days
```

#### Parallel Mailbox Sync

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

#### Custom Batch Processing

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

### FAQ

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

### Support

For issues or questions:
1. Check Celery logs: `docker logs -f subscriptions_celery`
2. Review this guide
3. Check OpenAI usage dashboard for rate limit status
4. Verify `.env` configuration matches your OpenAI tier

---

## Frontend Sync UI

Sync emails directly from the browser with customizable date ranges and
real-time progress tracking — no terminal access required.

### How to Use

#### Step 1: Navigate to Mailboxes Page

Go to the Mailboxes section in your app.

#### Step 2: Click "Sync Emails" Button

Each mailbox card has a blue "Sync Emails" button.

#### Step 3: Select Your Date Range

Choose from preset options:
- **Last 7 days** - Recent emails from the past week
- **Last 30 days** - Default sync period (1 month)
- **Last 90 days** - Last 3 months of emails
- **Last 180 days** - Last 6 months of emails
- **Last 365 days** - Full year of email history
- **Custom period** - Specify any number of days (1-3650)

#### Step 4: Start Sync

Click "Start Sync" and watch the progress in real-time!

### Progress Tracking

The sync modal provides comprehensive real-time feedback.

#### Real-Time Status Indicators

- **Queued** - Waiting to start
- **In Progress** - Actively processing
- **Completed** - Successfully finished
- **Failed** - Error occurred

#### Live Metrics

- **Emails Processed** - Count updates every 2 seconds
- **Subscriptions Found** - Real-time subscription detection
- **Time Elapsed** - How long the sync has been running
- **Progress Bar** - Visual indication of activity

#### Completion Summary

When finished, you'll see:
- Total emails processed
- Total subscriptions found
- Success/failure message
- Option to close and view results

### Auto-Refresh Behaviour

- Progress updates every 2 seconds
- Subscriptions page refreshes on completion
- Mailbox status updates automatically

### Safety Features

- Modal cannot be closed during an active sync (prevents accidental cancellation)
- Clear status indicators throughout
- Error messages displayed if sync fails
- Automatic cleanup of UI state on completion

### Example Use Cases

#### Initial Setup (Full Year)

1. Add your mailbox
2. Click "Sync Emails"
3. Select "Last 365 days"
4. Start sync
5. Wait 10-30 minutes (depending on email volume)
6. Review found subscriptions

#### Weekly Updates

1. Click "Sync Emails"
2. Select "Last 7 days"
3. Start sync
4. Completes in 1-2 minutes

#### Custom Historical Import

1. Click "Sync Emails"
2. Select "Custom period"
3. Enter days (e.g., 730 for 2 years)
4. Start sync

### Rate Limiting Notice

The sync modal displays a helpful notice:
> OpenAI API calls are rate-limited to prevent errors.
> Large syncs may take 10-30 minutes depending on email volume.

This ensures your syncs won't fail due to API rate limits.

### Time Estimates (Frontend)

With default rate limiting (1 second delay):

| Email Volume | Expected Duration |
|--------------|-------------------|
| 50 emails | 1-2 minutes |
| 100 emails | 2-3 minutes |
| 500 emails | 10-15 minutes |
| 1000 emails | 20-30 minutes |
| 5000+ emails | 1-3 hours |

### Tips for Large Syncs

#### 365-Day Syncs

1. Start the sync before leaving your desk
2. You can close the modal — the sync continues in background
3. Check back later to see results
4. Progress will resume if you reopen the modal

#### Regular Weekly Updates

1. Use 7-day syncs weekly
2. Quick and efficient
3. Catches new subscriptions

#### Testing / First Time

1. Use a 7-day sync first to verify everything works
2. Then run larger syncs (30, 90, or 365 days)

### Frontend Troubleshooting

#### Sync Stuck on "Queued"

- Wait 10-20 seconds for Celery worker to pick up the task
- Check Celery is running: `docker ps | grep celery`

#### Sync Failed

- Check error message in the modal
- Verify mailbox credentials
- Check Celery logs: `docker logs subscriptions_celery`

#### Progress Not Updating

- Wait 2-3 seconds (polling interval)
- Check network connection
- Refresh the page if necessary

#### No Subscriptions Found

- Verify emails in that period contain subscriptions
- Check AI Sandbox for uncertain emails
- Lower confidence threshold in settings if needed

#### Custom Date Range Not Working

Two issues were resolved in a recent version:

1. **Date filter was ignored**: Custom date ranges would be ignored if a mailbox had been synced before. Fixed — custom date ranges now take priority over the last sync timestamp.

2. **500 email limit**: Syncs were capped at 500 emails regardless of date range. Fixed — custom date syncs now fetch up to 50,000 emails to ensure complete coverage.

If you still experience issues:
- Ensure you're running the latest version (restart Celery: `docker restart subscriptions_celery`)
- Check Celery logs to verify the correct date and limit: `docker logs subscriptions_celery --tail 100`
- Look for log lines:
  - `"Using custom date filter: 365days (since [date])"`
  - `"Fetching emails since [date] with limit 50000"`

### UI vs Scripts Comparison

| Aspect | Frontend UI | CLI Scripts |
|--------|-------------|-------------|
| Interface | User-friendly, visual | Terminal-based |
| Progress tracking | Real-time in browser | Celery logs |
| Technical knowledge | None required | Terminal access needed |
| Flexibility | Predefined options + custom days | Full configuration control |
| Automation | Manual trigger | Can be scheduled with cron |
| Runs headlessly | No (modal, background possible) | Yes |

### Best Practices

1. **Start Small**: Test with 7-30 days first
2. **Monitor Progress**: Watch the first sync to understand timing
3. **Schedule Large Syncs**: Run 365-day syncs when you have time to wait
4. **Regular Updates**: Weekly 7-day syncs keep things current
5. **Check Results**: Review found subscriptions in AI Sandbox

### Next Steps After Syncing

1. Go to **AI Sandbox** to review uncertain emails
2. Visit **Subscriptions** page to see detected subscriptions
3. Edit/update subscription details as needed
4. Set up automatic weekly syncs if desired
