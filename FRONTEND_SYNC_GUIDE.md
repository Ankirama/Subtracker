# Frontend Email Sync Guide

## 🎉 New Feature: Sync from UI with Progress Tracking

You can now sync emails directly from the frontend with customizable date ranges and real-time progress tracking!

## How to Use

### 1. Navigate to Mailboxes Page

Go to the Mailboxes section in your app.

### 2. Click "Sync Emails" Button

Each mailbox card has a blue "Sync Emails" button.

### 3. Select Your Date Range

Choose from preset options:
- **Last 7 days** - Recent emails from the past week
- **Last 30 days** - Default sync period (1 month)
- **Last 90 days** - Last 3 months of emails
- **Last 180 days** - Last 6 months of emails
- **Last 365 days** - Full year of email history ⭐
- **Custom period** - Specify any number of days (1-3650)

### 4. Start Sync

Click "Start Sync" and watch the progress in real-time!

## Progress Tracking Features

The sync modal shows:

### Real-Time Status
- **Queued** - Waiting to start
- **In Progress** - Actively processing
- **Completed** - Successfully finished
- **Failed** - Error occurred

### Live Metrics
- **Emails Processed** - Count updates every 2 seconds
- **Subscriptions Found** - Real-time subscription detection
- **Time Elapsed** - How long the sync has been running
- **Progress Bar** - Visual indication of activity

### Completion Summary
When finished, you'll see:
- Total emails processed
- Total subscriptions found
- Success/failure message
- Option to close and view results

## Example Use Cases

### Initial Setup (Full Year)
1. Add your mailbox
2. Click "Sync Emails"
3. Select "Last 365 days"
4. Start sync
5. Wait 10-30 minutes (depending on email volume)
6. Review found subscriptions

### Weekly Updates
1. Click "Sync Emails"
2. Select "Last 7 days"
3. Start sync
4. Completes in 1-2 minutes

### Custom Historical Import
1. Click "Sync Emails"
2. Select "Custom period"
3. Enter days (e.g., 730 for 2 years)
4. Start sync

## Rate Limiting Protection

The sync modal displays a helpful notice:
> OpenAI API calls are rate-limited to prevent errors.
> Large syncs may take 10-30 minutes depending on email volume.

This ensures your syncs won't fail due to API rate limits!

## Time Estimates

With default rate limiting (1 second delay):

| Email Volume | Expected Duration |
|--------------|-------------------|
| 50 emails | 1-2 minutes |
| 100 emails | 2-3 minutes |
| 500 emails | 10-15 minutes |
| 1000 emails | 20-30 minutes |
| 5000+ emails | 1-3 hours |

## Features

### ✅ What You Can Do
- Select custom date ranges from the UI
- Track progress in real-time
- See live email and subscription counts
- Monitor time elapsed
- Get notified on completion
- Close modal and continue working (sync runs in background)

### 🔄 Auto-Refresh
- Progress updates every 2 seconds
- Subscriptions page refreshes on completion
- Mailbox status updates automatically

### 🛡️ Safety Features
- Can't close modal during sync (prevents accidental cancellation)
- Clear status indicators
- Error messages if sync fails
- Automatic cleanup of UI state

## Tips

### For Large Syncs (365 days)
1. Start the sync before leaving your desk
2. You can close the modal - sync continues in background
3. Check back later to see results
4. Progress will resume if you reopen the modal

### For Regular Updates
1. Use 7-day syncs weekly
2. Quick and efficient
3. Catches new subscriptions

### For Testing
1. Use 7-day sync first to verify everything works
2. Then run larger syncs (30, 90, or 365 days)

## Troubleshooting

### Sync Stuck on "Queued"
- Wait 10-20 seconds for Celery worker to pick up the task
- Check Celery is running: `docker ps | grep celery`

### Sync Failed
- Check error message in the modal
- Verify mailbox credentials
- Check Celery logs: `docker logs subscriptions_celery`

### Progress Not Updating
- Wait 2-3 seconds (polling interval)
- Check network connection
- Refresh the page if necessary

### No Subscriptions Found
- Verify emails in that period contain subscriptions
- Check AI Sandbox for uncertain emails
- Lower confidence threshold in settings if needed

### Custom Date Range Not Working
**Fixed in latest version!** Two issues were resolved:

1. **Date filter was ignored**: Custom date ranges would be ignored if a mailbox had been synced before. Fixed - custom date ranges now take priority over the last sync timestamp.

2. **500 email limit**: Syncs were capped at 500 emails regardless of date range. Fixed - custom date syncs now fetch up to 50,000 emails to ensure complete coverage.

If you still experience issues:
- Ensure you're running the latest version (restart Celery: `docker restart subscriptions_celery`)
- Check Celery logs to verify the correct date and limit: `docker logs subscriptions_celery --tail 100`
- Look for log lines:
  - "Using custom date filter: 365days (since [date])"
  - "Fetching emails since [date] with limit 50000"

## Comparison: UI vs Scripts

### Frontend UI ✨ (New!)
**Pros:**
- User-friendly interface
- Real-time progress tracking
- Visual feedback
- No technical knowledge needed
- Click and go

**Cons:**
- Requires browser open (can close modal though)
- Limited to predefined options

### Scripts 🖥️
**Pros:**
- Can run on server
- More flexible configuration
- Can be automated with cron

**Cons:**
- Requires terminal access
- Less visual feedback
- More technical

## Best Practices

1. **Start Small**: Test with 7-30 days first
2. **Monitor Progress**: Watch the first sync to understand timing
3. **Schedule Large Syncs**: Run 365-day syncs when you have time
4. **Regular Updates**: Weekly 7-day syncs keep things current
5. **Check Results**: Review found subscriptions in AI Sandbox

## Next Steps

After syncing:
1. Go to **AI Sandbox** to review uncertain emails
2. Visit **Subscriptions** page to see detected subscriptions
3. Edit/update subscription details as needed
4. Set up automatic weekly syncs if desired

---

Enjoy your new email syncing experience! 🎉
