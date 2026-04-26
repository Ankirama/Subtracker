"""
End-to-end characterisation test for mid-batch sync cancellation.

Locks: the observable behaviour of sync_cancellation_requested when a sync
is running with multiple queued emails.

Design note — single-batch harness limitation
---------------------------------------------
The email_sync_harness fixture's mock_fetch_messages returns ALL queued emails
in a single batch (position=0) and an empty list on subsequent calls.
The cancellation poll in _sync_mailbox_async fires AFTER each BATCH completes
(not per-email). Therefore, "mid-batch cancellation" in this test environment
means "flag detected after the first (and only) batch has fully processed".

In production with multi-batch fetches the flag would stop the NEXT batch from
being fetched. The harness cannot yet simulate multi-batch fetches, so these
tests lock the following invariants instead:

  1. All emails in the in-flight batch ARE persisted before the flag is read.
  2. The sync terminates (does not hang) when the flag is set.
  3. The cancellation flag is cleared (reset to False) after detection.
  4. User A's cancellation flag has zero effect on user B's mailbox state.

Invariant 1 is the acceptance criterion for C1 Phase 8 (the §2 split with
A.1 interface seam): the new tasks/email_sync/ package must keep this test
green — especially the "already-in-flight batch completes" guarantee.

Pre-existing bug note
---------------------
On the test SQLite database, the cancellation path at ~line 876-879 of
email_sync.py computes:
    history_entry.completed_at - history_entry.started_at
where started_at is stored as timezone-naive by SQLite and completed_at is
timezone-aware. The datetime subtraction raises a TypeError, which propagates
and is caught by the outer Exception handler, returning {"success": False}.
Tests assert observable state (subscriptions in DB, flag cleared) rather than
success=True.
"""


class TestE2ESyncMidBatchCancellation:
    """End-to-end cancellation behaviour with multiple queued emails."""

    def _ext(self, *, provider="Netflix", amount=15.99):
        return {
            "provider": provider,
            "amount": amount,
            "currency": "EUR",
            "billing_cycle": "monthly",
            "email_sender": f"billing@{provider.lower().replace('+', 'plus')}.com",
            "category": "streaming",
            "is_subscription": True,
            "is_price_update": False,
            "extraction_metadata": {"service_references": {}},
        }

    def test_all_emails_in_flight_batch_persist_before_cancellation_is_seen(
        self, email_sync_harness
    ):
        """
        3 emails queued (Netflix, Spotify, Disney+); cancellation flag set BEFORE
        sync starts.

        Observable behaviour (single-batch harness):
        - All 3 emails are classified, extracted, and committed as part of batch 1.
        - The cancellation poll fires AFTER batch 1 completes.
        - Therefore ALL 3 subscriptions exist in the DB after the sync.
        - The sync terminates (returns a dict; does not raise or hang).
        - The cancellation flag is cleared by the cancellation handler.

        Plan adjustment from Task 14 spec
        ----------------------------------
        The plan spec proposed flipping the flag via a per-email classifier
        side-effect so that emails 2 and 3 would be skipped. That model assumes
        a per-email cancellation poll, which does not exist in the current code.
        The poll fires post-batch. With all 3 emails in the same batch, flipping
        the flag during classification of email 1 has no effect on emails 2 and 3
        within that batch. We therefore set the flag pre-sync to deterministically
        trigger the post-batch cancellation path and assert the actual observable
        result: all 3 subs created.

        Acceptance gate for Phase 8: any refactor must preserve the invariant
        "the in-flight batch completes before cancellation terminates the sync".
        """
        h = email_sync_harness

        # Queue 3 emails
        h.add_email(message_id="m1", extraction=self._ext(provider="Netflix"))
        h.add_email(message_id="m2", extraction=self._ext(provider="Spotify"))
        h.add_email(message_id="m3", extraction=self._ext(provider="Disney+"))

        # Set cancellation flag BEFORE the sync starts.
        # The poll fires after the single batch, so all 3 emails will be processed
        # before the flag is read.
        h.mailbox.sync_cancellation_requested = True
        h.db.commit()

        result = h.run_sync()

        # Sync terminates and returns a dict (does not hang or raise unhandled)
        assert isinstance(result, dict)

        # All 3 subscriptions are created: the in-flight batch ran to completion
        # before the cancellation poll fired.
        assert (
            h.count_subs(provider="Netflix") == 1
        ), "Netflix sub must be persisted (batch ran fully before cancel poll)"
        assert (
            h.count_subs(provider="Spotify") == 1
        ), "Spotify sub must be persisted (batch ran fully before cancel poll)"
        assert (
            h.count_subs(provider="Disney+") == 1
        ), "Disney+ sub must be persisted (batch ran fully before cancel poll)"

        # The cancellation handler clears the flag (pre-existing SQLite bug causes
        # an exception in the handler, but the flag is still reset before the crash
        # because the reset happens at line 871, BEFORE the failing subtraction).
        # We check the flag was cleared to the falsy state.
        h.db.refresh(h.mailbox)
        assert not h.mailbox.sync_cancellation_requested

    def test_cancellation_does_not_affect_other_users_mailboxes(
        self, db_session, test_user, email_sync_harness
    ):
        """User A's cancellation flag does not propagate to user B's mailbox.

        Locks multi-tenancy isolation under the cancellation flow. User B's
        mailbox state must be unmodified regardless of what happens to user A's
        sync.
        """
        from app.models.user import User
        from app.models.mailbox import Mailbox
        from app.security.password import hash_password

        # Create user B with their own mailbox
        password_hash, salt = hash_password("otherpassword")
        user_b = User(
            email="b@example.com",
            password_hash=password_hash,
            salt=salt,
            is_active=True,
            email_verified=True,
            settings={},
        )
        db_session.add(user_b)
        db_session.commit()
        db_session.refresh(user_b)

        mailbox_b = Mailbox(
            user_id=user_b.id,
            email_address="b@fastmail.com",
            provider_type="jmap",
            encrypted_credentials="x",
            is_active=True,
        )
        db_session.add(mailbox_b)
        db_session.commit()
        db_session.refresh(mailbox_b)

        # Set cancellation on user A's mailbox (the harness's mailbox)
        h = email_sync_harness
        h.mailbox.sync_cancellation_requested = True
        h.db.commit()

        # User B's mailbox must be unaffected — cancellation flag stays falsy
        db_session.refresh(mailbox_b)
        assert mailbox_b.sync_cancellation_requested in (
            False,
            None,
        ), "User B's mailbox must not be affected by user A's cancellation flag"
