"""
Celery tasks for email verification cleanup and maintenance
"""

from datetime import datetime, timedelta
from celery.utils.log import get_task_logger

from app.celery_app import celery_app
from app.database import get_db
from app.models.user import User

logger = get_task_logger(__name__)


@celery_app.task(name="tasks.cleanup_unverified_users")
def cleanup_unverified_users():
    """
    Delete user accounts that haven't verified their email within 7 days.

    This task runs daily to maintain database hygiene and encourage timely
    email verification. Users can always re-register if needed.

    Returns:
        dict: Success status and count of deleted users
    """
    logger.info("Starting unverified user cleanup...")
    db = next(get_db())
    deleted_count = 0

    try:
        # Calculate cutoff date (7 days ago)
        cutoff_date = datetime.utcnow() - timedelta(days=7)

        # Find unverified users older than 7 days
        unverified_users = (
            db.query(User)
            .filter(not User.email_verified, User.created_at < cutoff_date)
            .all()
        )

        # Delete each unverified user
        for user in unverified_users:
            logger.info(
                f"Deleting unverified user: {user.email} (created: {user.created_at})"
            )
            db.delete(user)
            deleted_count += 1

        # Commit the deletions
        db.commit()

        logger.info(
            f"Unverified user cleanup completed. Deleted {deleted_count} user(s)"
        )
        return {"success": True, "deleted_count": deleted_count}

    except Exception as e:
        db.rollback()
        logger.error(f"Error in unverified user cleanup task: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        db.close()
