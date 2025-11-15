"""
JMAP (JSON Meta Application Protocol) email provider implementation.
Supports Fastmail and other JMAP-compatible providers.
"""
import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging

from app.email_providers.base import EmailProviderInterface, EmailMessage, EmailFolder

logger = logging.getLogger(__name__)


class JMAPProvider(EmailProviderInterface):
    """
    JMAP email provider implementation.

    Credentials required:
    - server_url: JMAP server URL (e.g., "https://api.fastmail.com/jmap/session")
    - username: Email address or username (used for display only)
    - password: App-specific Bearer token (e.g., Fastmail app password)

    Note: Uses Bearer token authentication for Fastmail compatibility.
    """

    def __init__(self, credentials: Dict[str, Any]):
        super().__init__(credentials)
        self.server_url = credentials.get('server_url')
        self.username = credentials.get('username')
        self.password = credentials.get('password')
        self.session_data = None
        self.account_id = None
        self.client = httpx.AsyncClient(timeout=30.0)

    async def authenticate(self) -> bool:
        """
        Authenticate with JMAP server and fetch session information.
        """
        try:
            # JMAP authentication uses Bearer token (for Fastmail)
            response = await self.client.get(
                self.server_url,
                headers={"Authorization": f"Bearer {self.password}"}
            )
            response.raise_for_status()

            self.session_data = response.json()

            # Get primary account ID
            self.account_id = self.session_data.get('primaryAccounts', {}).get('urn:ietf:params:jmap:mail')

            if not self.account_id:
                logger.error("No primary mail account found in JMAP session")
                return False

            self._authenticated = True
            logger.info(f"JMAP authentication successful for {self.username}")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(f"JMAP authentication failed: HTTP {e.response.status_code}")
            return False
        except Exception as e:
            logger.error(f"JMAP authentication error: {str(e)}")
            return False

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test JMAP connection and return account information.
        """
        try:
            if not self._authenticated:
                auth_success = await self.authenticate()
                if not auth_success:
                    return {
                        "success": False,
                        "message": "Authentication failed",
                        "info": {}
                    }

            # Fetch mailbox list to verify connection
            folders = await self.get_folders()

            return {
                "success": True,
                "message": "Connected successfully to JMAP server",
                "info": {
                    "account_id": self.account_id,
                    "username": self.username,
                    "server": self.server_url,
                    "folders_count": len(folders),
                    "capabilities": list(self.session_data.get('capabilities', {}).keys())
                }
            }

        except Exception as e:
            logger.error(f"JMAP connection test failed: {str(e)}")
            return {
                "success": False,
                "message": f"Connection test failed: {str(e)}",
                "info": {}
            }

    async def get_folders(self) -> List[EmailFolder]:
        """
        Fetch JMAP mailboxes.
        """
        if not self._authenticated:
            await self.authenticate()

        try:
            api_url = self.session_data['apiUrl']

            # JMAP request to get mailboxes
            request_payload = {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    [
                        "Mailbox/get",
                        {
                            "accountId": self.account_id,
                            "ids": None  # Get all mailboxes
                        },
                        "0"
                    ]
                ]
            }

            response = await self.client.post(
                api_url,
                json=request_payload,
                headers={"Authorization": f"Bearer {self.password}"}
            )
            response.raise_for_status()

            data = response.json()
            mailboxes = data['methodResponses'][0][1]['list']

            folders = []
            for mailbox in mailboxes:
                folders.append(EmailFolder(
                    id=mailbox['id'],
                    name=mailbox['name'],
                    message_count=mailbox.get('totalEmails', 0),
                    unread_count=mailbox.get('unreadEmails', 0)
                ))

            return folders

        except Exception as e:
            logger.error(f"Failed to fetch JMAP mailboxes: {str(e)}")
            raise

    async def fetch_messages(
        self,
        folder: Optional[str] = None,
        since_date: Optional[datetime] = None,
        limit: int = 100,
        search_query: Optional[str] = None
    ) -> List[EmailMessage]:
        """
        Fetch messages using JMAP Email/query and Email/get.
        """
        if not self._authenticated:
            await self.authenticate()

        try:
            api_url = self.session_data['apiUrl']

            # Build JMAP filter
            jmap_filter = {}
            if folder:
                jmap_filter['inMailbox'] = folder
            if since_date:
                # JMAP expects UTC time with Z suffix (RFC 3339)
                jmap_filter['after'] = since_date.strftime('%Y-%m-%dT%H:%M:%SZ')

            # First, query for email IDs
            query_request = {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    [
                        "Email/query",
                        {
                            "accountId": self.account_id,
                            "filter": jmap_filter if jmap_filter else None,
                            "sort": [{"property": "receivedAt", "isAscending": False}],
                            "limit": limit
                        },
                        "0"
                    ],
                    [
                        "Email/get",
                        {
                            "accountId": self.account_id,
                            "#ids": {
                                "resultOf": "0",
                                "name": "Email/query",
                                "path": "/ids"
                            },
                            "properties": [
                                "id", "subject", "from", "to", "receivedAt",
                                "bodyValues", "textBody", "htmlBody", "hasAttachment",
                                "mailboxIds", "headers"
                            ],
                            "fetchTextBodyValues": True,
                            "fetchHTMLBodyValues": True
                        },
                        "1"
                    ]
                ]
            }

            response = await self.client.post(
                api_url,
                json=query_request,
                headers={"Authorization": f"Bearer {self.password}"}
            )
            response.raise_for_status()

            data = response.json()
            emails_data = data['methodResponses'][1][1]['list']

            messages = []
            for email in emails_data:
                # Parse sender
                sender_info = email.get('from', [{}])[0]
                sender = sender_info.get('email', '')
                sender_name = sender_info.get('name')

                # Parse recipients
                recipients = [r.get('email', '') for r in email.get('to', [])]

                # Get body content
                body_values = email.get('bodyValues', {})
                text_body = None
                html_body = None

                if email.get('textBody'):
                    text_part_id = email['textBody'][0].get('partId')
                    if text_part_id and text_part_id in body_values:
                        text_body = body_values[text_part_id].get('value')

                if email.get('htmlBody'):
                    html_part_id = email['htmlBody'][0].get('partId')
                    if html_part_id and html_part_id in body_values:
                        html_body = body_values[html_part_id].get('value')

                # Parse headers
                headers = {}
                for header in email.get('headers', []):
                    headers[header['name']] = header['value']

                # Get folder (first mailbox)
                folder_name = None
                mailbox_ids = email.get('mailboxIds', {})
                if mailbox_ids:
                    folder_name = list(mailbox_ids.keys())[0]  # Simplified

                messages.append(EmailMessage(
                    id=email['id'],
                    subject=email.get('subject', ''),
                    sender=sender,
                    sender_name=sender_name,
                    recipients=recipients,
                    date=datetime.fromisoformat(email['receivedAt'].replace('Z', '+00:00')),
                    body_text=text_body,
                    body_html=html_body,
                    headers=headers,
                    has_attachments=email.get('hasAttachment', False),
                    folder=folder_name
                ))

            logger.info(f"Fetched {len(messages)} emails from JMAP")
            return messages

        except Exception as e:
            logger.error(f"Failed to fetch JMAP messages: {str(e)}", exc_info=True)
            raise

    async def get_message_by_id(self, message_id: str) -> Optional[EmailMessage]:
        """
        Fetch a specific email by ID.
        """
        if not self._authenticated:
            await self.authenticate()

        try:
            api_url = self.session_data['apiUrl']

            request_payload = {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    [
                        "Email/get",
                        {
                            "accountId": self.account_id,
                            "ids": [message_id],
                            "properties": [
                                "id", "subject", "from", "to", "receivedAt",
                                "bodyValues", "textBody", "htmlBody", "hasAttachment",
                                "mailboxIds", "headers"
                            ],
                            "fetchTextBodyValues": True,
                            "fetchHTMLBodyValues": True
                        },
                        "0"
                    ]
                ]
            }

            response = await self.client.post(
                api_url,
                json=request_payload,
                headers={"Authorization": f"Bearer {self.password}"}
            )
            response.raise_for_status()

            data = response.json()
            emails = data['methodResponses'][0][1].get('list', [])

            if not emails:
                return None

            email = emails[0]
            # Convert to EmailMessage (same logic as fetch_messages)
            # ... (implementation similar to above)

            return None  # Placeholder - implement conversion

        except Exception as e:
            logger.error(f"Failed to fetch message {message_id}: {str(e)}")
            return None

    async def mark_as_read(self, message_id: str) -> bool:
        """
        Mark an email as read in JMAP.
        """
        if not self._authenticated:
            await self.authenticate()

        try:
            api_url = self.session_data['apiUrl']

            request_payload = {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    [
                        "Email/set",
                        {
                            "accountId": self.account_id,
                            "update": {
                                message_id: {
                                    "keywords/$seen": True
                                }
                            }
                        },
                        "0"
                    ]
                ]
            }

            response = await self.client.post(
                api_url,
                json=request_payload,
                headers={"Authorization": f"Bearer {self.password}"}
            )
            response.raise_for_status()

            data = response.json()
            updated = data['methodResponses'][0][1].get('updated', {})

            return message_id in updated

        except Exception as e:
            logger.error(f"Failed to mark message as read: {str(e)}")
            return False

    async def close(self):
        """
        Close HTTP client connections.
        """
        await self.client.aclose()
        logger.info("JMAP client connections closed")
