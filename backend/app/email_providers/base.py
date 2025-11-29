"""
Base interface for email providers.
All email providers (JMAP, Gmail, Outlook) must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass


@dataclass
class EmailMessage:
    """
    Standardized email message format across all providers.
    """

    id: str  # Provider-specific message ID
    subject: str
    sender: str  # Email address
    sender_name: Optional[str]
    recipients: List[str]
    date: datetime
    body_text: Optional[str]  # Plain text body
    body_html: Optional[str]  # HTML body
    headers: Dict[str, str]  # Email headers
    has_attachments: bool
    folder: Optional[str]  # Folder/label name


@dataclass
class EmailFolder:
    """
    Standardized folder/mailbox information.
    """

    id: str
    name: str
    message_count: int
    unread_count: int


class EmailProviderInterface(ABC):
    """
    Abstract base class for email providers.
    All providers must implement these methods.
    """

    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize the provider with credentials.

        Args:
            credentials: Provider-specific credentials dict
        """
        self.credentials = credentials
        self._authenticated = False

    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Authenticate with the email provider.

        Returns:
            True if authentication successful, False otherwise

        Raises:
            Exception: If authentication fails
        """
        pass

    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test the connection and return provider information.

        Returns:
            Dict with keys: success (bool), message (str), info (dict)

        Example:
            {
                "success": True,
                "message": "Connected successfully",
                "info": {
                    "account_name": "user@example.com",
                    "total_messages": 1234,
                    "folders": 5
                }
            }
        """
        pass

    @abstractmethod
    async def fetch_messages(
        self,
        folder: Optional[str] = None,
        since_date: Optional[datetime] = None,
        limit: int = 100,
        search_query: Optional[str] = None,
    ) -> List[EmailMessage]:
        """
        Fetch messages from the mailbox.

        Args:
            folder: Folder/label to fetch from (None = all folders)
            since_date: Only fetch messages after this date (None = all)
            limit: Maximum number of messages to fetch
            search_query: Provider-specific search query

        Returns:
            List of EmailMessage objects

        Raises:
            Exception: If fetch fails
        """
        pass

    @abstractmethod
    async def get_folders(self) -> List[EmailFolder]:
        """
        Get list of folders/mailboxes.

        Returns:
            List of EmailFolder objects

        Raises:
            Exception: If fetch fails
        """
        pass

    @abstractmethod
    async def get_message_by_id(self, message_id: str) -> Optional[EmailMessage]:
        """
        Fetch a specific message by ID.

        Args:
            message_id: Provider-specific message ID

        Returns:
            EmailMessage object or None if not found

        Raises:
            Exception: If fetch fails
        """
        pass

    @abstractmethod
    async def mark_as_read(self, message_id: str) -> bool:
        """
        Mark a message as read.

        Args:
            message_id: Provider-specific message ID

        Returns:
            True if successful, False otherwise
        """
        pass

    async def close(self):
        """
        Close connections and clean up resources.
        Optional - override if needed.
        """
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__}(authenticated={self._authenticated})>"
