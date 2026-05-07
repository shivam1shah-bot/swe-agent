"""
Agents Catalogue Item model for the SWE Agent.
"""

import time
from sqlalchemy import Column, Integer, String, Text, Enum, Index
from .base import Base
import enum

class AgentsCatalogueItemType(enum.Enum):
    API = "api"
    MICROFRONTEND = "micro-frontend"
    WORKFLOW = "workflow"

class LifecycleStatus(enum.Enum):
    EXPERIMENTAL = "experimental"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"

class AgentsCatalogueItem(Base):
    """Agents Catalogue Item model for storing use case information"""
    __tablename__ = "agents_catalogue_items"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)  # Must be unique
    description = Column(Text, nullable=True)
    type = Column(Enum(AgentsCatalogueItemType, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    lifecycle = Column(Enum(LifecycleStatus, values_callable=lambda obj: [e.value for e in obj]), default=LifecycleStatus.EXPERIMENTAL)
    
    # Store as JSON strings
    owners = Column(Text, nullable=False)  # JSON array of email addresses
    tags = Column(Text, nullable=True)     # JSON array of predefined tags
    
    created_at = Column(Integer, default=lambda: int(time.time()))
    updated_at = Column(Integer, default=lambda: int(time.time()), onupdate=lambda: int(time.time()))

    # Add indexes for common queries
    __table_args__ = (
        Index('idx_name', 'name'),
        Index('idx_type', 'type'),
        Index('idx_lifecycle', 'lifecycle'),
        Index('idx_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<AgentsCatalogueItem(id={self.id}, name={self.name}, type={self.type.value})>" 