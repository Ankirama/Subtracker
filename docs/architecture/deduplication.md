# Subscription Deduplication

> Multi-factor scoring algorithm with a hard threshold, plus the PayPal → actual provider resolution rule.

When a freshly extracted subscription enters the pipeline, it is scored against every existing subscription for the same user. Scores ≥ 70 are treated as duplicates and auto-merged.

## Scoring Factors

| Factor | Weight | Rule |
|---|---:|---|
| Email sender similarity | 30 | Same/similar sender domain or address |
| Provider name fuzzy match | 40 | `fuzzy_match(threshold=0.85)` |
| Amount similarity | 20 | Within 5 % tolerance |
| Billing cycle match | 10 | Exact match (monthly/yearly/quarterly/...) |
| Same billing period | 10 | `same_billing_period(renewal_date_a, renewal_date_b)` |
| Payment-processor bonus | +50 | New email is from a known payment processor (PayPal etc.) AND the existing subscription's provider name appears in the new extraction |

Threshold: **70 points** = duplicate (auto-merge). Anything below 70 is treated as a new subscription.

## Multi-Factor Deduplication Logic

```python
def find_duplicates(new_subscription, existing_subscriptions):
    """
    Intelligent duplicate detection
    """
    duplicates = []

    for existing in existing_subscriptions:
        score = 0

        # Factor 1: Email sender similarity
        if similar_sender(new_subscription.email_sender, existing.email_sender):
            score += 30

        # Factor 2: Provider name match
        if fuzzy_match(new_subscription.provider, existing.provider, threshold=0.85):
            score += 40

        # Factor 3: Amount similarity (within 5%)
        if amounts_similar(new_subscription.amount, existing.amount, tolerance=0.05):
            score += 20

        # Factor 4: Billing cycle match
        if new_subscription.billing_cycle == existing.billing_cycle:
            score += 10

        # Factor 5: Time proximity (same month)
        if same_billing_period(new_subscription.renewal_date, existing.renewal_date):
            score += 10

        # Special case: Payment processor detection
        if is_payment_processor(new_subscription.email_sender):
            # Check if existing subscription matches the actual provider
            if new_subscription.provider in existing.provider:
                score += 50  # High confidence it's a duplicate via PayPal

        if score >= 70:  # Threshold for duplicate
            duplicates.append((existing, score))

    return duplicates
```

## Auto-Merge Logic

When a duplicate is detected, the merge prefers the non-payment-processor record (i.e. the entry with the actual service identity). PayPal/processor metadata is preserved on the kept record so that future PayPal-mediated emails resolve correctly.

```python
def auto_merge_duplicates(new_sub, duplicate_sub, merge_score):
    """
    Merge duplicate subscriptions, preferring non-payment-processor
    """
    if is_payment_processor(new_sub.email_sender):
        # Keep existing, store PayPal as metadata
        duplicate_sub.payment_processor = {
            "provider": "paypal",
            "email": new_sub.email_sender
        }
        duplicate_sub.save()
        return duplicate_sub
    else:
        # Update existing with new info if more reliable
        if new_sub.confidence_score > duplicate_sub.confidence_score:
            duplicate_sub.update_from(new_sub)
        duplicate_sub.last_confirmed_at = datetime.now()
        duplicate_sub.save()
        return duplicate_sub
```

## PayPal → Actual Provider Resolution

PayPal (and other payment-processor) emails do not name the underlying service in their sender. The `+50` payment-processor bonus, combined with a substring match between the extraction's `provider` and an existing subscription's `provider`, is the mechanism that prevents PayPal emails from creating duplicate subscriptions.

The merged record stores `payment_processor` as JSONB on `subscriptions`:

```json
{"provider": "paypal", "email": "service@paypal.com"}
```

This metadata makes the relationship explicit and queryable.

## `custom_label` Disambiguation

Same-provider, multi-instance subscriptions (e.g. multiple Twitch streamer subscriptions) are NOT treated as duplicates because the `custom_label` column on `subscriptions` differentiates them at the data-model level (see data-model.md §3.3). The dedup function above does not currently consult `custom_label`; the design relies on the user setting different labels post-detection.

## Test (excerpt)

```python
@pytest.mark.asyncio
async def test_deduplication():
    deduplicator = Deduplicator(user_id="test")
    # Create existing subscription
    existing = create_subscription(provider="Netflix", amount=15.99)

    # New email from PayPal for Netflix
    new_data = {
        "provider": "Netflix",
        "amount": 15.99,
        "email_sender": "service@paypal.com"
    }

    duplicates = deduplicator.find_duplicates(new_data)
    assert len(duplicates) == 1
    assert duplicates[0].id == existing.id
```
