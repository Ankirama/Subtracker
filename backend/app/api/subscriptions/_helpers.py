"""Shared helpers for subscription API sub-modules."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.mailbox import Mailbox


def verify_mailbox_ownership(mailbox_id: UUID, user_id: UUID, db: Session) -> Mailbox:
    """Verify that the mailbox belongs to the current user."""
    mailbox = (
        db.query(Mailbox)
        .filter(Mailbox.id == mailbox_id, Mailbox.user_id == user_id)
        .first()
    )

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mailbox not found or not authorized",
        )

    return mailbox
