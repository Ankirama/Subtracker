-- Migration: Add subscription feedback table for AI improvement
-- Created: 2024-01-17

-- Create enum for feedback types
CREATE TYPE feedback_type AS ENUM (
    'not_subscription',
    'duplicate',
    'wrong_amount',
    'wrong_provider',
    'wrong_category',
    'wrong_billing_cycle',
    'other'
);

-- Create subscription_feedback table
CREATE TABLE subscription_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id UUID NOT NULL,  -- Not FK because subscription might be deleted

    -- Feedback details
    feedback_type feedback_type NOT NULL,
    feedback_text TEXT,  -- Optional additional explanation

    -- Snapshot of subscription data for analysis
    subscription_snapshot JSONB NOT NULL,  -- Store full subscription data before deletion

    -- AI classification data that led to this detection
    ai_classification_data JSONB,  -- Store AI reasoning and confidence scores

    -- Related emails that caused the misclassification
    source_email_ids UUID[] DEFAULT '{}',

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for analysis queries
CREATE INDEX idx_subscription_feedback_user_id ON subscription_feedback(user_id);
CREATE INDEX idx_subscription_feedback_type ON subscription_feedback(feedback_type);
CREATE INDEX idx_subscription_feedback_created_at ON subscription_feedback(created_at);

-- Add comment for documentation
COMMENT ON TABLE subscription_feedback IS 'Stores user feedback on AI-detected subscriptions to improve classification accuracy';
COMMENT ON COLUMN subscription_feedback.subscription_snapshot IS 'Full subscription data snapshot before deletion for analysis';
COMMENT ON COLUMN subscription_feedback.ai_classification_data IS 'AI reasoning and confidence scores from classification';
COMMENT ON COLUMN subscription_feedback.source_email_ids IS 'Email IDs that led to this subscription detection';
