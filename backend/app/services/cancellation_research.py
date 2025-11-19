"""
AI-powered cancellation research service.
Uses OpenAI GPT to research how to cancel subscription services.
"""
from openai import AsyncOpenAI, RateLimitError, APIError
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timedelta
from app.config import settings
from app.models.provider_cancellation import ProviderCancellationInfo, DifficultyRating, InstructionsSource
from app.utils.config_helper import get_config_value
from app.services.ai_classifier import get_openai_client
import logging
import json
import asyncio

logger = logging.getLogger(__name__)


CANCELLATION_RESEARCH_PROMPT = """You are a helpful AI assistant that researches how to cancel subscription services.

Your task is to provide accurate, step-by-step instructions for cancelling a subscription to {provider_name}.

Please research and provide the following information in JSON format:

1. **cancellation_url**: The direct URL where users can cancel (if available, otherwise null)
2. **difficulty**: How hard it is to cancel - choose one:
   - "easy": Can be cancelled in 1-2 clicks online with no friction
   - "medium": Requires 3-5 steps, navigating through account settings
   - "hard": Requires phone call, live chat, or complex process

3. **instructions**: Array of clear, step-by-step instructions. Each step should be specific and actionable.
   Example: ["Go to account.example.com/settings", "Click 'Manage Subscription'", "Click 'Cancel Subscription'", "Confirm cancellation"]

4. **requires_phone**: true if cancellation requires calling customer service
5. **requires_chat**: true if cancellation requires live chat
6. **allows_pause**: true if the service allows pausing instead of cancelling
7. **pause_instructions**: Array of steps to pause (if applicable, otherwise null)
8. **additional_notes**: Important warnings, timing considerations, or refund policies (string or null)
9. **estimated_minutes**: Estimated time in minutes to complete cancellation (number or null)
10. **gotchas**: Array of common pitfalls or things to watch out for (array or null)
    Example: ["Must cancel 24 hours before renewal", "No refunds for partial months"]

11. **confidence**: Your confidence score from 0.0 to 1.0 in the accuracy of this information
12. **sources**: Brief description of information sources (string or null)

IMPORTANT GUIDELINES:
- Be accurate and helpful - users depend on this information
- If you're not certain about something, indicate lower confidence
- Prioritize recent information (2023-2025)
- Focus on the most common/standard cancellation process
- If multiple methods exist, provide the easiest one
- Be specific about timing (e.g., "24 hours before renewal" not "before renewal")

Return ONLY valid JSON with these exact keys. No markdown, no explanations outside the JSON.

Example response format:
{{
  "cancellation_url": "https://account.netflix.com/cancelplan",
  "difficulty": "easy",
  "instructions": ["Log in to netflix.com", "Click your profile icon", "Select 'Account'", "Click 'Cancel Membership'", "Confirm cancellation"],
  "requires_phone": false,
  "requires_chat": false,
  "allows_pause": false,
  "pause_instructions": null,
  "additional_notes": "Access continues until end of billing period. No refunds for partial months.",
  "estimated_minutes": 2.0,
  "gotchas": ["No refunds for unused time", "Must download content before access ends"],
  "confidence": 0.9,
  "sources": "Official Netflix help center and recent user reports (2024)"
}}
"""


class CancellationResearchService:
    """
    Service for researching subscription cancellation instructions using AI.
    """

    def __init__(self, db: Session):
        """
        Initialize the research service.

        Args:
            db: Database session for storing/retrieving research results
        """
        self.db = db
        self.client = None  # Lazy initialization

    def _get_client(self) -> AsyncOpenAI:
        """Get OpenAI client with configuration"""
        if self.client is None:
            self.client = get_openai_client(self.db)
        return self.client

    async def research_provider(
        self,
        provider_name: str,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Research cancellation instructions for a provider using AI.

        Checks cache first (database), only makes API call if:
        - No cached result exists
        - Cached result is >90 days old
        - force_refresh is True

        Args:
            provider_name: Name of subscription provider (e.g., "Netflix")
            force_refresh: Force new research even if cached result exists

        Returns:
            Dictionary with research results including instructions and metadata

        Raises:
            ValueError: If provider_name is invalid
            RateLimitError: If OpenAI API rate limit exceeded
            APIError: If OpenAI API call fails
        """
        if not provider_name or not provider_name.strip():
            raise ValueError("provider_name cannot be empty")

        provider_name = provider_name.strip()

        # Check cache first (unless force_refresh)
        if not force_refresh:
            cached = await self._get_cached_research(provider_name)
            if cached:
                logger.info(f"Using cached cancellation info for {provider_name}")
                return cached

        # No cache or force refresh - research with AI
        logger.info(f"Researching cancellation instructions for {provider_name} with AI")

        try:
            research_result = await self._call_openai_research(provider_name)

            # Store result in database
            await self._store_research_result(provider_name, research_result)

            return research_result

        except RateLimitError as e:
            logger.error(f"OpenAI rate limit exceeded while researching {provider_name}: {e}")
            raise
        except APIError as e:
            logger.error(f"OpenAI API error while researching {provider_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error researching {provider_name}: {e}")
            raise

    async def _get_cached_research(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """
        Check if we have cached research results for this provider.

        Returns None if:
        - No result exists
        - Result is >90 days old

        Args:
            provider_name: Provider to check

        Returns:
            Cached research result or None
        """
        stmt = select(ProviderCancellationInfo).where(
            ProviderCancellationInfo.provider_name.ilike(provider_name)
        )
        result = self.db.execute(stmt)
        cached = result.scalar_one_or_none()

        if not cached:
            return None

        # Check age
        if cached.created_at and cached.created_at < datetime.now(cached.created_at.tzinfo) - timedelta(days=90):
            logger.info(f"Cached result for {provider_name} is >90 days old, will refresh")
            return None

        # Return cached result in API format
        return {
            "provider_name": cached.provider_name,
            "cancellation_url": cached.cancellation_url,
            "difficulty": cached.difficulty_rating.value,
            "instructions": cached.instructions or [],
            "requires_phone": cached.requires_phone_call,
            "requires_chat": cached.requires_chat,
            "allows_pause": cached.allows_pause,
            "pause_instructions": cached.pause_instructions,
            "additional_notes": cached.additional_notes,
            "estimated_minutes": cached.estimated_time_minutes,
            "gotchas": cached.cancellation_gotchas,
            "confidence": cached.ai_confidence_score or 0.0,
            "cached": True,
            "cached_at": cached.created_at.isoformat() if cached.created_at else None,
        }

    async def _call_openai_research(self, provider_name: str) -> Dict[str, Any]:
        """
        Call OpenAI API to research cancellation instructions.

        Args:
            provider_name: Provider to research

        Returns:
            Parsed research results

        Raises:
            ValueError: If response cannot be parsed
        """
        client = self._get_client()

        # Format prompt with provider name
        prompt = CANCELLATION_RESEARCH_PROMPT.format(provider_name=provider_name)

        try:
            # Call OpenAI with GPT-4o-mini (cost efficient)
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful research assistant that provides accurate subscription cancellation information in JSON format."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent, factual responses
                response_format={"type": "json_object"},  # Ensure JSON response
            )

            # Extract and parse JSON response
            content = response.choices[0].message.content
            research_data = json.loads(content)

            # Validate required fields
            required_fields = [
                "difficulty", "instructions", "requires_phone",
                "requires_chat", "allows_pause", "confidence"
            ]
            for field in required_fields:
                if field not in research_data:
                    raise ValueError(f"Missing required field: {field}")

            # Add provider name and metadata
            research_data["provider_name"] = provider_name
            research_data["cached"] = False
            research_data["researched_at"] = datetime.utcnow().isoformat()

            logger.info(f"Successfully researched {provider_name} (confidence: {research_data['confidence']})")

            return research_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response for {provider_name}: {e}")
            raise ValueError(f"Invalid JSON response from OpenAI: {e}")
        except KeyError as e:
            logger.error(f"Missing field in OpenAI response for {provider_name}: {e}")
            raise ValueError(f"Incomplete research data: {e}")

    async def _store_research_result(
        self,
        provider_name: str,
        research_data: Dict[str, Any]
    ) -> ProviderCancellationInfo:
        """
        Store research results in database.

        Args:
            provider_name: Provider name
            research_data: Research results from AI

        Returns:
            Created/updated ProviderCancellationInfo record
        """
        # Check if already exists
        stmt = select(ProviderCancellationInfo).where(
            ProviderCancellationInfo.provider_name.ilike(provider_name)
        )
        result = self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        # Get difficulty as lowercase string (database enum expects lowercase)
        difficulty_str = research_data["difficulty"].lower()
        if difficulty_str not in ("easy", "medium", "hard"):
            difficulty_str = "medium"  # Default to medium if invalid

        if existing:
            # Update existing record
            existing.cancellation_url = research_data.get("cancellation_url")
            existing.difficulty_rating = difficulty_str
            existing.instructions = research_data.get("instructions", [])
            existing.instructions_source = InstructionsSource.AI_GENERATED.value
            existing.requires_phone_call = research_data.get("requires_phone", False)
            existing.requires_chat = research_data.get("requires_chat", False)
            existing.allows_pause = research_data.get("allows_pause", False)
            existing.pause_instructions = research_data.get("pause_instructions")
            existing.additional_notes = research_data.get("additional_notes")
            existing.estimated_time_minutes = research_data.get("estimated_minutes")
            existing.cancellation_gotchas = research_data.get("gotchas")
            existing.ai_confidence_score = research_data.get("confidence", 0.0)
            existing.ai_research_prompt = CANCELLATION_RESEARCH_PROMPT.format(provider_name=provider_name)
            existing.ai_research_response = json.dumps(research_data)
            existing.updated_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(existing)

            logger.info(f"Updated cached cancellation info for {provider_name}")
            return existing

        else:
            # Create new record
            new_info = ProviderCancellationInfo(
                provider_name=provider_name,
                cancellation_url=research_data.get("cancellation_url"),
                difficulty_rating=difficulty_str,
                instructions=research_data.get("instructions", []),
                instructions_source=InstructionsSource.AI_GENERATED.value,
                requires_phone_call=research_data.get("requires_phone", False),
                requires_chat=research_data.get("requires_chat", False),
                allows_pause=research_data.get("allows_pause", False),
                pause_instructions=research_data.get("pause_instructions"),
                additional_notes=research_data.get("additional_notes"),
                estimated_time_minutes=research_data.get("estimated_minutes"),
                cancellation_gotchas=research_data.get("gotchas"),
                ai_confidence_score=research_data.get("confidence", 0.0),
                ai_research_prompt=CANCELLATION_RESEARCH_PROMPT.format(provider_name=provider_name),
                ai_research_response=json.dumps(research_data),
            )

            self.db.add(new_info)
            self.db.commit()
            self.db.refresh(new_info)

            logger.info(f"Stored new cancellation info for {provider_name}")
            return new_info


async def research_cancellation(
    provider_name: str,
    db: Session,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to research cancellation instructions.

    Args:
        provider_name: Provider to research
        db: Database session
        force_refresh: Force new research

    Returns:
        Research results dictionary
    """
    service = CancellationResearchService(db)
    return await service.research_provider(provider_name, force_refresh)
