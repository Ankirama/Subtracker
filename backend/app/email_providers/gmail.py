"""
Gmail email provider implementation using Gmail API with OAuth2.
"""

import base64
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging
from email.utils import parsedate_to_datetime

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.email_providers.base import EmailProviderInterface, EmailMessage, EmailFolder

logger = logging.getLogger(__name__)


class GmailAuthError(Exception):
    """
    Raised when Gmail authentication fails due to token issues.

    Attributes:
        message: Human-readable error message
        needs_reconnect: If True, user needs to re-authenticate via OAuth
    """
    def __init__(self, message: str, needs_reconnect: bool = False):
        self.message = message
        self.needs_reconnect = needs_reconnect
        super().__init__(message)


class GmailProvider(EmailProviderInterface):
    """
    Gmail email provider implementation using Gmail API.

    Credentials required:
    - access_token: OAuth2 access token
    - refresh_token: OAuth2 refresh token
    - token_expiry: Token expiration timestamp
    - client_id: Google OAuth client ID
    - client_secret: Google OAuth client secret
    """

    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    def __init__(self, credentials: Dict[str, Any]):
        super().__init__(credentials)
        self.access_token = credentials.get("access_token")
        self.refresh_token = credentials.get("refresh_token")
        self.token_expiry = credentials.get("token_expiry")
        self.client_id = credentials.get("client_id")
        self.client_secret = credentials.get("client_secret")
        self.email_address = credentials.get("email_address")
        self.service = None
        self._creds = None
        # Gmail pagination state
        self._page_token = None
        self._last_query = None

    def _get_credentials(self) -> Credentials:
        """Build Google credentials object from stored tokens."""
        creds = Credentials(
            token=self.access_token,
            refresh_token=self.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=self.SCOPES,
        )

        # Check if token needs refresh
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Update stored tokens
                self.access_token = creds.token
                self.token_expiry = creds.expiry.isoformat() if creds.expiry else None
                logger.info("Gmail access token refreshed successfully")
            except RefreshError as e:
                # Token refresh failed - user needs to re-authenticate
                error_msg = str(e)
                logger.error(f"Gmail token refresh failed (needs reconnect): {error_msg}")
                raise GmailAuthError(
                    message=f"Gmail authentication expired. Please reconnect your account.",
                    needs_reconnect=True
                )
            except Exception as e:
                logger.error(f"Failed to refresh Gmail token: {e}")
                raise GmailAuthError(
                    message=f"Gmail token refresh failed: {str(e)}",
                    needs_reconnect=True
                )

        return creds

    async def authenticate(self) -> bool:
        """
        Authenticate with Gmail API using stored OAuth tokens.

        Raises:
            GmailAuthError: If authentication fails due to token issues
        """
        try:
            self._creds = self._get_credentials()
            self.service = build("gmail", "v1", credentials=self._creds)

            # Test authentication by fetching profile
            profile = self.service.users().getProfile(userId="me").execute()
            self.email_address = profile.get("emailAddress")

            self._authenticated = True
            logger.info(f"Gmail authentication successful for {self.email_address}")
            return True

        except GmailAuthError:
            # Re-raise our custom auth errors
            raise
        except HttpError as e:
            status = e.resp.status
            logger.error(f"Gmail authentication failed: HTTP {status}")
            # 401 Unauthorized or 403 Forbidden indicate auth issues
            if status in (401, 403):
                raise GmailAuthError(
                    message=f"Gmail authentication failed (HTTP {status}). Please reconnect your account.",
                    needs_reconnect=True
                )
            return False
        except Exception as e:
            logger.error(f"Gmail authentication error: {str(e)}")
            return False

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test Gmail connection and return account information.
        """
        try:
            if not self._authenticated:
                auth_success = await self.authenticate()
                if not auth_success:
                    return {
                        "success": False,
                        "message": "Authentication failed",
                        "info": {},
                    }

            # Fetch profile and labels to verify connection
            profile = self.service.users().getProfile(userId="me").execute()
            labels = self.service.users().labels().list(userId="me").execute()

            return {
                "success": True,
                "message": "Connected successfully to Gmail",
                "info": {
                    "email_address": profile.get("emailAddress"),
                    "total_messages": profile.get("messagesTotal", 0),
                    "total_threads": profile.get("threadsTotal", 0),
                    "labels_count": len(labels.get("labels", [])),
                    "history_id": profile.get("historyId"),
                },
            }

        except Exception as e:
            logger.error(f"Gmail connection test failed: {str(e)}")
            return {
                "success": False,
                "message": f"Connection test failed: {str(e)}",
                "info": {},
            }

    async def fetch_messages(
        self,
        folder: Optional[str] = None,
        since_date: Optional[datetime] = None,
        limit: int = 100,
        search_query: Optional[str] = None,
        position: int = 0,
    ) -> tuple[List[EmailMessage], bool]:
        """
        Fetch messages from Gmail with proper pageToken-based pagination.

        Gmail uses pageToken for pagination. The position parameter indicates
        whether this is a new query (position=0) or a continuation (position>0).
        PageTokens are stored in instance variables between calls.

        Args:
            folder: Gmail label to filter by
            since_date: Only fetch messages after this date
            limit: Max messages per batch (Gmail API max is 500)
            search_query: Additional search query
            position: 0 for new query, >0 for continuation

        Returns:
            Tuple of (messages, has_more) where has_more indicates more pages exist
        """
        if not self._authenticated:
            await self.authenticate()

        messages = []
        query_parts = []

        # Build Gmail search query
        if folder:
            query_parts.append(f"label:{folder}")

        if since_date:
            # Gmail uses YYYY/MM/DD format for date queries
            date_str = since_date.strftime("%Y/%m/%d")
            query_parts.append(f"after:{date_str}")

        if search_query:
            query_parts.append(search_query)

        query = " ".join(query_parts) if query_parts else None

        # Reset pageToken if this is a new query (position=0)
        if position == 0:
            self._page_token = None
            self._last_query = query
            logger.info(f"Gmail: Starting new query pagination (limit={limit})")
        elif query != self._last_query:
            # Query changed, reset pagination
            logger.warning("Gmail: Query changed mid-pagination, resetting")
            self._page_token = None
            self._last_query = query

        try:
            # Build API request with pageToken if available
            request_params = {
                "userId": "me",
                "q": query,
                "maxResults": min(limit, 500),  # Gmail API limit is 500
            }

            if self._page_token:
                request_params["pageToken"] = self._page_token
                logger.info(f"Gmail: Fetching page with token (limit={limit})")

            # List message IDs
            results = self.service.users().messages().list(**request_params).execute()

            message_refs = results.get("messages", [])
            next_page_token = results.get("nextPageToken")

            # Store pageToken for next call
            self._page_token = next_page_token

            logger.info(
                f"Gmail API returned {len(message_refs)} message IDs, "
                f"has_more={bool(next_page_token)}"
            )

            # Fetch full message details
            for msg_ref in message_refs:
                try:
                    msg = (
                        self.service.users()
                        .messages()
                        .get(userId="me", id=msg_ref["id"], format="full")
                        .execute()
                    )

                    email_msg = self._parse_message(msg)
                    if email_msg:
                        messages.append(email_msg)
                except Exception as e:
                    logger.warning(f"Failed to fetch message {msg_ref['id']}: {e}")
                    continue

            # Return has_more based on presence of nextPageToken
            has_more = bool(next_page_token)

            logger.info(
                f"Gmail: Fetched {len(messages)} messages, "
                f"has_more={has_more}, "
                f"position={position}"
            )

            return messages, has_more

        except HttpError as e:
            logger.error(f"Gmail fetch failed: HTTP {e.resp.status}")
            raise
        except Exception as e:
            logger.error(f"Gmail fetch error: {str(e)}")
            raise

    def _parse_message(self, msg: Dict) -> Optional[EmailMessage]:
        """Parse Gmail API message into EmailMessage object."""
        try:
            headers = {
                h["name"].lower(): h["value"]
                for h in msg.get("payload", {}).get("headers", [])
            }

            # Extract sender
            from_header = headers.get("from", "")
            sender_email = from_header
            if "<" in from_header and ">" in from_header:
                sender_email = from_header.split("<")[1].split(">")[0]

            # Extract recipients
            to_header = headers.get("to", "")
            recipients = []
            if to_header:
                # Simple parsing - could be improved
                recipients = [r.strip() for r in to_header.split(",")]

            # Extract date
            date_str = headers.get("date", "")
            message_date = None
            if date_str:
                try:
                    message_date = parsedate_to_datetime(date_str)
                except Exception:
                    # Fallback to internal date
                    internal_date = msg.get("internalDate")
                    if internal_date:
                        message_date = datetime.fromtimestamp(
                            int(internal_date) / 1000, tz=timezone.utc
                        )

            # Extract body
            body_text = self._extract_body(msg.get("payload", {}))

            # Determine folder from labels
            label_ids = msg.get("labelIds", [])
            folder = None
            if "INBOX" in label_ids:
                folder = "INBOX"
            elif label_ids:
                folder = label_ids[0]

            return EmailMessage(
                id=msg["id"],
                subject=headers.get("subject", "(No Subject)"),
                sender=sender_email,
                sender_name=(
                    from_header.split("<")[0].strip().strip('"')
                    if "<" in from_header
                    else None
                ),
                recipients=recipients,
                date=message_date or datetime.now(timezone.utc),
                body_text=body_text,
                body_html=None,  # Could extract HTML version if needed
                headers=headers,
                has_attachments=any(
                    part.get("filename")
                    for part in msg.get("payload", {}).get("parts", [])
                ),
                folder=folder,
            )
        except Exception as e:
            logger.warning(f"Failed to parse Gmail message: {e}")
            return None

    def _extract_body(self, payload: Dict) -> str:
        """Extract plain text body from Gmail message payload."""
        body_text = ""

        # Check for direct body data
        if "body" in payload and payload["body"].get("data"):
            try:
                body_text = base64.urlsafe_b64decode(payload["body"]["data"]).decode(
                    "utf-8", errors="replace"
                )
                return body_text
            except Exception:
                pass

        # Check for multipart message
        if "parts" in payload:
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")

                if mime_type == "text/plain":
                    if part.get("body", {}).get("data"):
                        try:
                            body_text = base64.urlsafe_b64decode(
                                part["body"]["data"]
                            ).decode("utf-8", errors="replace")
                            return body_text
                        except Exception:
                            continue

                # Recursively check nested parts
                if "parts" in part:
                    nested_text = self._extract_body(part)
                    if nested_text:
                        return nested_text

        return body_text

    async def get_folders(self) -> List[EmailFolder]:
        """
        Get list of Gmail labels as folders.
        """
        if not self._authenticated:
            await self.authenticate()

        folders = []
        try:
            results = self.service.users().labels().list(userId="me").execute()
            labels = results.get("labels", [])

            for label in labels:
                # Get detailed label info
                label_detail = (
                    self.service.users()
                    .labels()
                    .get(userId="me", id=label["id"])
                    .execute()
                )

                folders.append(
                    EmailFolder(
                        id=label["id"],
                        name=label["name"],
                        role=label.get("type", "user").lower(),
                        total_messages=label_detail.get("messagesTotal", 0),
                        unread_count=label_detail.get("messagesUnread", 0),
                    )
                )

            return folders

        except Exception as e:
            logger.error(f"Failed to fetch Gmail labels: {e}")
            raise

    async def get_message_by_id(self, message_id: str) -> Optional[EmailMessage]:
        """
        Fetch a specific message by ID.
        """
        if not self._authenticated:
            await self.authenticate()

        try:
            msg = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            return self._parse_message(msg)

        except HttpError as e:
            if e.resp.status == 404:
                return None
            raise
        except Exception as e:
            logger.error(f"Failed to fetch Gmail message {message_id}: {e}")
            raise

    async def mark_as_read(self, message_id: str) -> bool:
        """
        Mark a message as read (remove UNREAD label).
        """
        if not self._authenticated:
            await self.authenticate()

        try:
            self.service.users().messages().modify(
                userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to mark Gmail message as read: {e}")
            return False

    async def close(self):
        """Clean up resources."""
        self.service = None
        self._creds = None

    def get_updated_credentials(self) -> Dict[str, Any]:
        """
        Get updated credentials after potential token refresh.
        Useful for storing refreshed tokens back to database.
        """
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expiry": self.token_expiry,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "email_address": self.email_address,
        }
