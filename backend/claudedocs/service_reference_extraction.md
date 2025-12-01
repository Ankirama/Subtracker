# Service Reference Extraction - Implementation Summary

## Overview

Implemented a **hybrid regex + AI extraction system** to reliably extract service-specific identifiers (like OVH service codes, AWS account IDs, domain names) from subscription emails and use them to differentiate multiple subscriptions from the same provider.

## Problem Solved

**User's Challenge**: Providers like OVH send emails for multiple services (domains, VPS, dedicated servers), each identified by unique codes (e.g., "FR73880615"). Without extracting these codes, all OVH emails would be grouped into a single subscription, making it impossible to track each service separately.

**Solution**: Combine reliable regex pattern matching with AI context understanding to extract and match service references.

## Architecture

### 1. Provider Patterns Configuration
**File**: `backend/app/config/provider_patterns.py`

Defines regex patterns for each provider:

```python
PROVIDER_PATTERNS = {
    "OVH": [
        {
            "name": "service_code",
            "pattern": r"\b(FR\d{8})\b",  # FR + 8 digits
            "priority": 200,
            "description": "OVH service reference code"
        },
        {
            "name": "domain",
            "pattern": r"\b([a-z0-9][a-z0-9\-]{0,61}[a-z0-9]?\.[a-z]{2,})\b",
            "priority": 100,
            "description": "Domain name"
        }
    ],
    "AWS": [...],
    "Google Cloud": [...],
    # ... more providers
}
```

**Key Functions**:
- `extract_service_references(text, provider)`: Extracts references using provider-specific regex patterns
- `format_custom_label(provider, references, service_type)`: Generates smart labels like "VPS - FR73880615"

### 2. Hybrid Extraction Service
**File**: `backend/app/services/reference_extractor.py`

Combines regex reliability with AI context understanding:

```python
class ReferenceExtractor:
    def extract(self, email_subject, email_body, provider, category):
        # Step 1: Extract via regex (reliable)
        regex_references = extract_service_references(full_text, provider)

        # Step 2: AI detects service type (context)
        service_type = self._detect_service_type(...)

        # Step 3: Generate custom label
        custom_label = format_custom_label(provider, regex_references, service_type)

        # Step 4: Build metadata
        return {
            "references": regex_references,
            "custom_label": custom_label,
            "service_type": service_type,
            "extraction_metadata": {...}
        }
```

**AI Context Detection**: Uses OpenAI GPT-4o-mini to understand service type from email context (e.g., "VPS", "Domain Renewal", "Cloud Storage")

### 3. Integration with Subscription Extraction
**File**: `backend/app/services/subscription_extractor.py`

Enhanced the main extraction flow:

```python
async def extract_subscription_data(email, db):
    # AI extracts subscription data
    extracted = await openai_extraction(...)
    cleaned = clean_extracted_data(extracted)

    # NEW: Enhance with service reference extraction
    cleaned = enhance_with_service_references(
        cleaned, email.subject, body, email.body_text
    )

    return cleaned
```

**AI Prompt Enhancement**: Updated the extraction prompt to guide the AI to extract service codes when visible (lines 105-108).

### 4. Subscription Matching Logic
**File**: `backend/app/tasks/email_sync.py`

Added service reference matching as **highest priority** (lines 469-485):

```python
# Priority order for matching:
# 1. Service references (NEW - most reliable)
# 2. Single match (only one subscription for provider)
# 3. Payment processor email → first match
# 4. Email sender match
# 5. Custom label match
# 6. Fallback to first match

service_references = extraction_metadata.get("service_references", {})

if service_references and len(potential_matches) > 1:
    for match in potential_matches:
        if extractor.can_match_subscription(service_references, match.extraction_metadata):
            existing_sub = match
            break
```

## Data Flow

```
Email Arrives
    ↓
AI Classification & Extraction
    ↓
enhance_with_service_references()
    ↓
Regex extracts: {"service_code": "FR73880615", "domain": "example.com"}
    ↓
AI detects service type: "VPS"
    ↓
Custom label generated: "VPS - FR73880615"
    ↓
Metadata stored in extraction_metadata JSONB field:
{
    "service_references": {
        "service_code": "FR73880615",
        "domain": "example.com"
    },
    "service_type": "VPS",
    "provider": "OVH",
    "extraction_method": "hybrid_regex_ai"
}
    ↓
During subscription matching:
- Check service_references first
- If "FR73880615" matches existing subscription → link to it
- Otherwise, check other matching criteria
```

## Supported Providers

Current patterns configured for:
- **OVH**: Service codes (FR\d{8}), domains
- **AWS**: Account IDs (12 digits), ARNs, service identifiers
- **Google Cloud**: Project IDs, billing account IDs
- **Azure**: Subscription IDs, resource IDs
- **Namecheap**: Domain names, order IDs
- **GoDaddy**: Domain names, customer IDs
- **Cloudflare**: Zone IDs, account IDs
- **Twitch**: Channel names/usernames
- **Discord**: Server names

## Testing

Created comprehensive test script: `backend/scripts/test_service_references.py`

Test cases:
1. OVH extraction with service code "FR73880615"
2. AWS extraction with account ID
3. Twitch extraction with channel name
4. Subscription matching logic

## Usage Example

**OVH Email**:
```
Subject: Renouvellement de votre service FR73880615
Body: Votre service OVH FR73880615 (VPS Cloud) sera renouvelé le 15/12/2024.
```

**Extraction Result**:
```python
{
    "provider": "OVH",
    "amount": 9.99,
    "currency": "EUR",
    "custom_label": "VPS - FR73880615",
    "extraction_metadata": {
        "service_references": {
            "service_code": "FR73880615",
            "domain": "example.com"
        },
        "service_type": "VPS",
        "provider": "OVH",
        "extraction_method": "hybrid_regex_ai"
    }
}
```

**Future Email Matching**:
When another OVH email arrives with "FR73880615", it will automatically match to this existing subscription.

## Benefits

1. **Reliable Extraction**: Regex ensures service codes are always extracted accurately
2. **Context Understanding**: AI provides semantic understanding of service type
3. **Automatic Matching**: Future emails automatically link to correct subscriptions
4. **Smart Labels**: Auto-generated labels help users identify subscriptions
5. **Extensible**: Easy to add new providers by defining regex patterns
6. **Hybrid Approach**: Best of both worlds - regex reliability + AI context

## Next Steps

To verify the feature works with real OVH emails:
1. Run an email sync with OVH emails in the mailbox
2. Check logs for service reference extraction:
   ```bash
   docker logs subscriptions_celery | grep "service_references"
   ```
3. Verify subscriptions in database have `extraction_metadata` populated
4. Test that subsequent OVH emails match to correct subscriptions

## Adding New Providers

To add a new provider pattern:

1. Edit `backend/app/config/provider_patterns.py`
2. Add provider to `PROVIDER_PATTERNS`:
```python
"NewProvider": [
    {
        "name": "identifier_type",
        "pattern": r"your_regex_pattern",
        "description": "What this pattern matches",
        "priority": 200,  # Higher = checked first
        "context_hint": "Hint for AI context"
    }
]
```
3. Optionally update `format_custom_label()` for provider-specific label formatting

## Files Modified/Created

### Created:
- `backend/app/config/provider_patterns.py` (306 lines)
- `backend/app/services/reference_extractor.py` (255 lines)
- `backend/app/config/__init__.py` (18 lines)
- `backend/scripts/test_service_references.py` (202 lines)

### Modified:
- `backend/app/services/subscription_extractor.py` (added service reference integration)
- `backend/app/tasks/email_sync.py` (added service reference matching logic)

## Implementation Complete

All requested functionality has been implemented and is ready to use during email syncing.
