# AI Strategy

> OpenAI Assistant configuration, two-stage processing (classify → extract), confidence-based routing, and the learning loop from user corrections.

## Provider and Model

- **Provider**: OpenAI
- **Model**: GPT-4o-mini (configurable per user via `users.settings`)
- **Integration**: OpenAI Assistants API
- **Fallback**: Direct API calls for simple extraction

Why an Assistant rather than direct API:
- Maintains conversation context for iterative extraction.
- Function calling produces structured output natively.
- Instructions can be updated without code changes.
- Falls back to direct API if needed.

## OpenAI Assistant Configuration

```python
assistant = client.beta.assistants.create(
    name="Subscription Email Analyzer",
    instructions="""You are an expert at analyzing emails to identify subscription-related communications.

Your task is two-fold:
1. CLASSIFICATION: Determine if an email is about a subscription (recurring payment)
2. EXTRACTION: If yes, extract structured subscription data

CLASSIFICATION CRITERIA:
- Look for recurring payment language (monthly, yearly, subscription, renewal)
- Identify billing/payment notifications
- Detect service provider names
- Be cautious with one-time purchases or receipts
- Support both French and English emails

EXTRACTION REQUIREMENTS:
Extract these fields:
- provider: Company/service name
- amount: Numeric value only
- currency: 3-letter code (EUR, USD, etc.)
- billing_cycle: monthly, yearly, quarterly, or other
- renewal_date: YYYY-MM-DD format if available
- subscription_id: Any subscription/account ID if present

EDGE CASES:
- PayPal/payment processor emails: Extract the actual service provider, not PayPal
- Multiple subscriptions in one email: Extract the primary one
- Gifts/trials: Mark as subscription only if recurring payment confirmed
- Cancellation emails: Mark as subscription but note if cancelled

Return confidence score (0-100) for your classification.""",
    model="gpt-4o-mini",
    tools=[
        {
            "type": "function",
            "function": {
                "name": "extract_subscription_data",
                "description": "Extract structured subscription information from email",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "is_subscription": {
                            "type": "boolean",
                            "description": "Is this a subscription-related email?"
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score 0-100"
                        },
                        "provider": {"type": "string"},
                        "amount": {"type": "number"},
                        "currency": {"type": "string"},
                        "billing_cycle": {
                            "type": "string",
                            "enum": ["monthly", "yearly", "quarterly", "other"]
                        },
                        "renewal_date": {"type": "string"},
                        "subscription_id": {"type": "string"},
                        "reasoning": {
                            "type": "string",
                            "description": "Brief explanation of classification decision"
                        }
                    },
                    "required": ["is_subscription", "confidence", "reasoning"]
                }
            }
        }
    ]
)
```

## Template-Based Extraction (Phase 1)

Template matching runs first. A successful template match returns confidence 100 % and bypasses the AI for both classification and extraction. Templates are hardcoded for common providers in Phase 1 and become user-creatable in Phase 2.

```python
TEMPLATES = {
    "netflix": {
        "sender_pattern": r".*@netflix\.com",
        "subject_pattern": r".*payment|receipt|invoice.*",
        "extraction": {
            "amount": r"(?:€|EUR|USD|\$)\s*([0-9]+\.?[0-9]{0,2})",
            "billing_cycle": "monthly",  # default
            "provider": "Netflix"
        }
    },
    "spotify": {
        "sender_pattern": r".*@spotify\.com",
        "subject_pattern": r".*receipt|payment.*",
        "extraction": {
            "amount": r"([0-9]+\.?[0-9]{0,2})\s*(?:€|EUR|USD|\$)",
            "billing_cycle": "monthly",
            "provider": "Spotify"
        }
    },
    # Add more common providers...
}
```

Templates are persisted in the `email_templates` table (see data-model.md §3.8) and have a `priority` column so higher-priority patterns are checked first.

## Two-Stage Processing

### Stage 1: Classification

```python
def classify_email(email_content: str) -> tuple[bool, float]:
    """
    Returns: (is_subscription, confidence_score)
    """
    # Try template matching first
    for template in TEMPLATES.values():
        if matches_template(email_content, template):
            return True, 100.0  # Perfect confidence for known patterns

    # Fall back to AI classification
    response = openai_assistant.classify(email_content)
    return response.is_subscription, response.confidence
```

### Stage 2: Extraction

```python
def extract_subscription_data(email_content: str, classification_confidence: float):
    """
    Extract structured data from email
    """
    # Try template extraction
    template_match = find_matching_template(email_content)
    if template_match:
        return extract_with_template(email_content, template_match)

    # Use AI extraction
    return openai_assistant.extract(email_content)
```

## Confidence-Based Routing

After classification + extraction (with optional dedup), each email is routed by its confidence score:

| Confidence | Action |
|---|---|
| ≥ 85 % | Auto-accept — subscription created automatically |
| 50 % – 84 % | Manual review — surfaced in the review queue |
| < 50 % | Rejected — still stored on `email_processing_records` for visibility |

Thresholds are configurable per user via `users.settings.confidence_thresholds`:

```json
{
  "confidence_thresholds": {
    "auto_accept": 85.0,
    "manual_review_min": 50.0
  }
}
```

## Learning from User Feedback

When a user manually accepts an email that was rejected or sent for review, the corrected extraction is stored as a few-shot example for future prompts. If a recurring pattern emerges, the system surfaces a suggestion to create a new template.

```python
def learn_from_acceptance(email_record, user_corrections):
    """
    Store as few-shot example for future prompts
    """
    training_example = {
        "email_subject": email_record.email_subject,
        "email_body_snippet": email_record.get_body_snippet(),
        "correct_extraction": user_corrections,
        "original_confidence": email_record.classification_confidence,
        "accepted_at": datetime.now()
    }

    # Store in database for later use in prompts
    store_training_example(training_example)

    # Optionally: suggest creating a template if pattern detected
    if should_suggest_template(training_example):
        notify_admin_for_template_creation(training_example)
```
