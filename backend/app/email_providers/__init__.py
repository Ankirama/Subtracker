# Email providers package
from app.email_providers.base import EmailProviderInterface, EmailMessage, EmailFolder
from app.email_providers.jmap import JMAPProvider

__all__ = ["EmailProviderInterface", "EmailMessage", "EmailFolder", "JMAPProvider"]
