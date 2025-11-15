# Future Enhancement: Payment Receipt Tracking

## Overview
Implement a payment receipt classification system to distinguish payment confirmations (PayPal, Stripe, etc.) from actual subscription emails and link them to existing subscriptions for payment history tracking.

## Current Approach (Option 1)
**Status:** ✅ Active
- PayPal/Stripe receipts are marked as "Not a Subscription"
- Use bulk action in AI Sandbox to efficiently mark payment receipts
- Prevents duplicate subscriptions
- Simple and clean data management

## Future Enhancement (Option 3)
**Status:** 📋 Planned

### Goals
1. Automatically detect payment receipts vs subscription emails
2. Avoid creating duplicate subscriptions from payment confirmations
3. Preserve payment history data
4. Link payment receipts to existing subscriptions
5. Display payment timeline on subscription details

### Implementation Plan

#### Phase 1: Enhanced AI Classification
**Backend Changes:**
1. Update AI classifier prompt to detect payment receipts
2. Add new classification category: `payment_receipt`
3. Update EmailMessage model to support new category
4. Migration to add category field if needed

**Classification Logic:**
```python
Categories:
- subscription_email: New subscription or renewal notification from service provider
- payment_receipt: Payment confirmation from payment processor (PayPal, Stripe, etc.)
- not_subscription: Regular emails, marketing, etc.
```

#### Phase 2: Payment Receipt Storage
**Database Schema:**
```python
# New table: payment_receipts
class PaymentReceipt(Base):
    id: UUID (PK)
    subscription_id: UUID (FK, nullable) # Linked subscription
    email_message_id: UUID (FK)
    payment_processor: str  # paypal, stripe, apple_pay, google_pay
    transaction_id: str
    amount: Decimal
    currency: str
    payment_date: DateTime
    payment_method: str  # credit_card, debit_card, bank_transfer
    payment_status: str  # completed, pending, failed
    matched_automatically: bool
    confidence_score: float
    created_at: DateTime
```

#### Phase 3: Matching Logic
**Automatic Matching Rules:**
1. **By Service Name:**
   - Extract service name from receipt (e.g., "Twitch" from PayPal receipt)
   - Match to subscription.provider
   - Confidence: High if exact match

2. **By Amount:**
   - Match payment amount to subscription.amount
   - Allow small variance (fees, taxes)
   - Confidence: Medium

3. **By Date Proximity:**
   - Match payment date near subscription.renewal_date
   - Within ±7 days of expected renewal
   - Confidence: Medium

4. **Combined Score:**
   - Service name match: 60%
   - Amount match: 30%
   - Date proximity: 10%
   - Minimum confidence: 0.7 for auto-link

**Manual Linking:**
- If confidence < 0.7, mark as "unlinked payment receipt"
- User can manually link in UI
- Show suggested matches based on score

#### Phase 4: Payment Extraction
**AI Extraction Prompt:**
```
Extract payment information from this receipt:
- Payment processor (PayPal, Stripe, Apple Pay, etc.)
- Transaction ID
- Amount paid
- Currency
- Payment date
- Service/merchant name
- Payment method (last 4 digits if available)
- Payment status

Return as structured JSON.
```

#### Phase 5: Frontend UI

**1. AI Sandbox Updates:**
```typescript
// New filter option
<Button>Payment Receipts ({data?.payment_receipts || 0})</Button>

// Payment receipt detail view
- Transaction details
- Suggested subscription matches
- Link/Unlink actions
```

**2. Subscription Detail Page:**
```typescript
// New "Payment History" section
<Accordion>
  <AccordionItem>
    <AccordionButton>Payment History</AccordionButton>
    <AccordionPanel>
      <Timeline>
        {payments.map(payment => (
          <TimelineItem>
            <Date>{payment.payment_date}</Date>
            <Amount>{payment.amount}</Amount>
            <Processor>{payment.payment_processor}</Processor>
            <Status>{payment.payment_status}</Status>
          </TimelineItem>
        ))}
      </Timeline>
    </AccordionPanel>
  </AccordionItem>
</Accordion>
```

**3. Dashboard Analytics:**
```typescript
// Payment method breakdown
- Credit card: 60%
- PayPal: 30%
- Other: 10%

// Payment status tracking
- On-time payments
- Failed payments
- Upcoming payments
```

### API Endpoints

#### New Endpoints
```python
POST /api/payment-receipts/classify
- Classify email as payment receipt
- Extract payment details
- Attempt automatic matching

GET /api/payment-receipts/unlinked
- List unlinked payment receipts
- Show suggested matches

POST /api/payment-receipts/{id}/link
- Manually link receipt to subscription

GET /api/subscriptions/{id}/payment-history
- Get payment timeline for subscription

POST /api/payment-receipts/{id}/unlink
- Unlink receipt from subscription
```

### Benefits

**For Users:**
- Complete payment history for each subscription
- Identify payment method changes
- Detect failed payments
- No duplicate subscriptions
- Better financial tracking

**For System:**
- Clean data without duplicates
- Rich payment metadata
- Payment analytics capabilities
- Better subscription lifecycle tracking

### Challenges to Consider

1. **Matching Accuracy:**
   - Service names may differ (Netflix vs Netflix Inc.)
   - Amounts may include fees/taxes
   - Multiple subscriptions to same service

2. **Payment Processor Variations:**
   - Different email formats per processor
   - Different data fields available
   - Internationalization issues

3. **Edge Cases:**
   - One payment for multiple subscriptions (bundle)
   - Partial payments / payment plans
   - Refunds and chargebacks
   - Currency conversions

### Implementation Priority
**Priority:** Medium
**Estimated Effort:** 3-5 days
**Dependencies:** None (additive feature)

### Future Extensions

1. **Payment Alerts:**
   - Notify on failed payments
   - Alert on payment method expiring
   - Reminder before large payments

2. **Payment Analytics:**
   - Payment method distribution
   - Average processing fees
   - Payment success rate

3. **Multi-Currency Support:**
   - Track original currency
   - Convert to primary currency
   - Show exchange rates used

4. **Receipt Attachments:**
   - Store PDF receipts
   - Link to email attachments
   - Export for tax purposes

## Related Files
- `backend/app/services/ai_classifier.py` - Classification logic
- `backend/app/services/subscription_extractor.py` - Extraction logic
- `frontend/src/components/ai-sandbox/` - Review UI
- `frontend/src/components/subscriptions/SubscriptionDetailPage.tsx` - Payment history display
