#!/usr/bin/env python3
"""
Test script for CancellationResearchService.
Tests AI-powered cancellation research with real providers.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.cancellation_research import (
    CancellationResearchService,
    research_cancellation,
)
from app.models.provider_cancellation import ProviderCancellationInfo
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def print_research_result(result: dict, title: str = "Research Result"):
    """Pretty print research result"""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")
    print(f"Provider: {result['provider_name']}")
    print(f"Cached: {result.get('cached', False)}")
    print(f"Confidence: {result.get('confidence', 0.0):.2f}")
    print(f"\nCancellation URL: {result.get('cancellation_url', 'N/A')}")
    print(f"Difficulty: {result.get('difficulty', 'N/A')}")
    print(f"Requires Phone: {result.get('requires_phone', False)}")
    print(f"Requires Chat: {result.get('requires_chat', False)}")
    print(f"Allows Pause: {result.get('allows_pause', False)}")
    print(f"Estimated Time: {result.get('estimated_minutes', 'N/A')} minutes")

    print(f"\nInstructions ({len(result.get('instructions', []))} steps):")
    for i, step in enumerate(result.get("instructions", []), 1):
        print(f"  {i}. {step}")

    if result.get("pause_instructions"):
        print(f"\nPause Instructions ({len(result['pause_instructions'])} steps):")
        for i, step in enumerate(result["pause_instructions"], 1):
            print(f"  {i}. {step}")

    if result.get("gotchas"):
        print(f"\n⚠️ Gotchas:")
        for gotcha in result["gotchas"]:
            print(f"  - {gotcha}")

    if result.get("additional_notes"):
        print(f"\n📝 Notes: {result['additional_notes']}")

    print(f"{'='*80}\n")


async def test_provider_research(
    db: Session, provider: str, force_refresh: bool = False
):
    """Test research for a single provider"""
    try:
        logger.info(f"Testing research for {provider} (force_refresh={force_refresh})")

        service = CancellationResearchService(db)
        result = await service.research_provider(provider, force_refresh=force_refresh)

        print_research_result(result, f"✅ Research Result: {provider}")

        # Validate required fields
        required_fields = [
            "difficulty",
            "instructions",
            "requires_phone",
            "requires_chat",
            "allows_pause",
            "confidence",
        ]
        missing_fields = [field for field in required_fields if field not in result]

        if missing_fields:
            logger.error(f"❌ Missing required fields: {missing_fields}")
            return False

        # Validate data types
        if not isinstance(result["instructions"], list):
            logger.error(
                f"❌ Instructions should be a list, got {type(result['instructions'])}"
            )
            return False

        if not (0.0 <= result["confidence"] <= 1.0):
            logger.error(
                f"❌ Confidence should be between 0.0 and 1.0, got {result['confidence']}"
            )
            return False

        logger.info(f"✅ {provider} research validation passed")
        return True

    except Exception as e:
        logger.error(f"❌ Error testing {provider}: {e}", exc_info=True)
        return False


async def test_caching(db: Session, provider: str):
    """Test that caching works correctly"""
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing cache functionality for {provider}")
    logger.info(f"{'='*80}\n")

    # First call - should hit API
    logger.info("📡 First call (should hit OpenAI API)...")
    result1 = await research_cancellation(provider, db, force_refresh=False)
    cached1 = result1.get("cached", False)

    if cached1:
        logger.warning("⚠️ First call was cached (unexpected if database was empty)")
    else:
        logger.info("✅ First call hit API as expected")

    # Second call - should use cache
    logger.info("\n💾 Second call (should use cache)...")
    result2 = await research_cancellation(provider, db, force_refresh=False)
    cached2 = result2.get("cached", False)

    if cached2:
        logger.info("✅ Second call used cache as expected")
    else:
        logger.error("❌ Second call hit API (should have used cache)")
        return False

    # Force refresh - should hit API again
    logger.info("\n🔄 Third call with force_refresh (should hit API)...")
    result3 = await research_cancellation(provider, db, force_refresh=True)
    cached3 = result3.get("cached", False)

    if not cached3:
        logger.info("✅ Force refresh hit API as expected")
    else:
        logger.error("❌ Force refresh used cache (should have hit API)")
        return False

    logger.info("\n✅ Cache functionality test passed!")
    return True


async def test_error_handling(db: Session):
    """Test error handling with invalid inputs"""
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing error handling")
    logger.info(f"{'='*80}\n")

    service = CancellationResearchService(db)

    # Test empty provider name
    try:
        await service.research_provider("")
        logger.error("❌ Should have raised ValueError for empty provider name")
        return False
    except ValueError as e:
        logger.info(f"✅ Correctly raised ValueError for empty provider: {e}")

    # Test whitespace-only provider name
    try:
        await service.research_provider("   ")
        logger.error(
            "❌ Should have raised ValueError for whitespace-only provider name"
        )
        return False
    except ValueError as e:
        logger.info(f"✅ Correctly raised ValueError for whitespace: {e}")

    logger.info("\n✅ Error handling test passed!")
    return True


async def test_database_storage(db: Session, provider: str):
    """Test that research results are stored in database correctly"""
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing database storage for {provider}")
    logger.info(f"{'='*80}\n")

    # Research provider
    await research_cancellation(provider, db, force_refresh=True)

    # Query database
    from sqlalchemy import select

    stmt = select(ProviderCancellationInfo).where(
        ProviderCancellationInfo.provider_name.ilike(provider)
    )
    result = db.execute(stmt)
    stored = result.scalar_one_or_none()

    if not stored:
        logger.error(f"❌ No record found in database for {provider}")
        return False

    logger.info(f"✅ Found database record:")
    logger.info(f"  - ID: {stored.id}")
    logger.info(f"  - Provider: {stored.provider_name}")
    logger.info(f"  - Difficulty: {stored.difficulty_rating.value}")
    logger.info(f"  - Instructions: {len(stored.instructions or [])} steps")
    logger.info(f"  - Source: {stored.instructions_source.value}")
    logger.info(f"  - AI Confidence: {stored.ai_confidence_score}")
    logger.info(f"  - Created: {stored.created_at}")
    logger.info(f"  - Updated: {stored.updated_at}")

    # Validate stored data
    if not stored.instructions:
        logger.error("❌ Instructions not stored")
        return False

    if not stored.ai_confidence_score:
        logger.error("❌ AI confidence score not stored")
        return False

    logger.info("\n✅ Database storage test passed!")
    return True


async def main():
    """Run all tests"""
    db = SessionLocal()

    try:
        logger.info("🧪 Starting CancellationResearchService Tests\n")

        # Test providers
        test_providers = ["Netflix", "Spotify", "Disney+"]

        # Test 1: Error handling
        logger.info("\n📋 Test 1: Error Handling")
        error_test_passed = await test_error_handling(db)

        # Test 2: Research for each provider
        logger.info("\n📋 Test 2: Provider Research")
        research_results = []
        for provider in test_providers:
            passed = await test_provider_research(db, provider, force_refresh=True)
            research_results.append((provider, passed))
            await asyncio.sleep(1)  # Be nice to OpenAI API

        # Test 3: Caching
        logger.info("\n📋 Test 3: Caching Functionality")
        cache_test_passed = await test_caching(db, "Netflix")

        # Test 4: Database storage
        logger.info("\n📋 Test 4: Database Storage")
        db_test_passed = await test_database_storage(db, "Spotify")

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("📊 TEST SUMMARY")
        logger.info("=" * 80)
        logger.info(
            f"Error Handling: {'✅ PASSED' if error_test_passed else '❌ FAILED'}"
        )
        for provider, passed in research_results:
            logger.info(
                f"Research ({provider}): {'✅ PASSED' if passed else '❌ FAILED'}"
            )
        logger.info(f"Caching: {'✅ PASSED' if cache_test_passed else '❌ FAILED'}")
        logger.info(
            f"Database Storage: {'✅ PASSED' if db_test_passed else '❌ FAILED'}"
        )
        logger.info("=" * 80)

        all_passed = (
            error_test_passed
            and all(passed for _, passed in research_results)
            and cache_test_passed
            and db_test_passed
        )

        if all_passed:
            logger.info("\n🎉 ALL TESTS PASSED!")
            return 0
        else:
            logger.error("\n❌ SOME TESTS FAILED")
            return 1

    except Exception as e:
        logger.error(f"❌ Test suite failed: {e}", exc_info=True)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
