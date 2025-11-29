#!/usr/bin/env python3
"""Simple test to isolate the issue"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.database import SessionLocal
from app.services.cancellation_research import research_cancellation


async def main():
    db = SessionLocal()
    try:
        print("Testing Netflix research...")
        result = await research_cancellation("Netflix", db, force_refresh=True)
        print("\n✅ SUCCESS!")
        print(f"Provider: {result['provider_name']}")
        print(f"Confidence: {result.get('confidence', 0.0)}")
        print(f"Cached: {result.get('cached', False)}")
        print(f"Instructions: {len(result.get('instructions', []))} steps")

        # Check database
        from sqlalchemy import select
        from app.models.provider_cancellation import ProviderCancellationInfo

        stmt = select(ProviderCancellationInfo).where(
            ProviderCancellationInfo.provider_name.ilike("Netflix")
        )
        db_result = db.execute(stmt)
        stored = db_result.scalar_one_or_none()

        if stored:
            print("\n✅ Found in database:")
            print(f"  Provider: {stored.provider_name}")
            print(f"  Difficulty: {stored.difficulty_rating.value}")
            print(f"  Instructions: {len(stored.instructions or [])} steps")
        else:
            print("\n❌ NOT found in database")

        return 0
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
