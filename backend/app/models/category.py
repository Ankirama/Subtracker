"""
SQLAlchemy model for custom subscription categories.
"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


# Default categories with assigned colors (Chakra UI color schemes)
DEFAULT_CATEGORIES = {
    'streaming': {'display_name': 'Streaming', 'color': 'red'},
    'software': {'display_name': 'Software', 'color': 'blue'},
    'storage': {'display_name': 'Storage', 'color': 'cyan'},
    'productivity': {'display_name': 'Productivity', 'color': 'purple'},
    'entertainment': {'display_name': 'Entertainment', 'color': 'pink'},
    'fitness': {'display_name': 'Fitness', 'color': 'green'},
    'gaming': {'display_name': 'Gaming', 'color': 'orange'},
    'news': {'display_name': 'News', 'color': 'yellow'},
    'education': {'display_name': 'Education', 'color': 'teal'},
    'communication': {'display_name': 'Communication', 'color': 'messenger'},
    'finance': {'display_name': 'Finance', 'color': 'whatsapp'},
    'shopping': {'display_name': 'Shopping', 'color': 'linkedin'},
    'music': {'display_name': 'Music', 'color': 'telegram'},
    'other': {'display_name': 'Other', 'color': 'gray'}
}


class Category(Base):
    """
    Custom subscription category created by users.

    Default categories are always available and don't need to be in this table.
    This table only stores user-created custom categories.
    """
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)  # Category name (lowercase, no spaces)
    display_name = Column(String(100), nullable=False)  # Display name (can have spaces, capitalization)
    color = Column(String(50), nullable=False, server_default='gray')  # Chakra UI color scheme
    is_default = Column(Boolean, default=False, nullable=False)  # True for default categories
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", backref="custom_categories")

    def __repr__(self):
        return f"<Category {self.name} (user_id={self.user_id})>"
