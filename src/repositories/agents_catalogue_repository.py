"""
Agents Catalogue repository for the SWE Agent.

Provides data access operations for AgentsCatalogueItem entities.
"""

import re
from abc import abstractmethod
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_, and_

from .base import BaseRepository, SQLAlchemyBaseRepository
from .exceptions import EntityNotFoundError, QueryExecutionError, TransactionError
from src.models.agents_catalogue_item import AgentsCatalogueItem, AgentsCatalogueItemType, LifecycleStatus
from src.providers.logger import Logger

class AgentsCatalogueRepository(BaseRepository[AgentsCatalogueItem]):
    """
    Abstract Agents Catalogue repository interface.
    
    Defines agents catalogue-specific data access operations.
    """
    
    @abstractmethod
    def get_by_type(self, item_type: AgentsCatalogueItemType, limit: Optional[int] = None) -> List[AgentsCatalogueItem]:
        """Get items by type."""
        pass
    
    @abstractmethod
    def get_by_lifecycle(self, lifecycle: LifecycleStatus, limit: Optional[int] = None) -> List[AgentsCatalogueItem]:
        """Get items by lifecycle status."""
        pass
    
    @abstractmethod
    def search_by_name_or_tags(self, query: str, limit: Optional[int] = None) -> List[AgentsCatalogueItem]:
        """Search items by name or tags."""
        pass
    
    @abstractmethod
    def check_name_exists(self, name: str, exclude_id: Optional[str] = None) -> bool:
        """Check if a name already exists."""
        pass
    
    @abstractmethod
    def get_paginated(self, offset: int, limit: int, filters: Optional[Dict[str, Any]] = None) -> List[AgentsCatalogueItem]:
        """Get paginated results with optional filters."""
        pass
    
    @abstractmethod
    def count_items(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count total items with optional filters."""
        pass


class SQLAlchemyAgentsCatalogueRepository(SQLAlchemyBaseRepository[AgentsCatalogueItem], AgentsCatalogueRepository):
    """
    SQLAlchemy implementation of AgentsCatalogueRepository.
    """
    
    def __init__(self, session: Session):
        """Initialize the agents catalogue repository."""
        super().__init__(session, AgentsCatalogueItem)
        self.logger = Logger("AgentsCatalogueRepository")
    
    def get_by_type(self, item_type: AgentsCatalogueItemType, limit: Optional[int] = None) -> List[AgentsCatalogueItem]:
        """Get items by type using SQLAlchemy."""
        try:
            query = self.session.query(AgentsCatalogueItem).filter(AgentsCatalogueItem.type == item_type)
            query = query.order_by(AgentsCatalogueItem.created_at.desc())
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
        except SQLAlchemyError as e:
            self.logger.error("Failed to get items by type", item_type=str(item_type), error=str(e))
            raise QueryExecutionError(f"get_by_type({item_type})", str(e))
    
    def get_by_lifecycle(self, lifecycle: LifecycleStatus, limit: Optional[int] = None) -> List[AgentsCatalogueItem]:
        """Get items by lifecycle status using SQLAlchemy."""
        try:
            query = self.session.query(AgentsCatalogueItem).filter(AgentsCatalogueItem.lifecycle == lifecycle)
            query = query.order_by(AgentsCatalogueItem.updated_at.desc())
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
        except SQLAlchemyError as e:
            self.logger.error("Failed to get items by lifecycle", lifecycle=str(lifecycle), error=str(e))
            raise QueryExecutionError(f"get_by_lifecycle({lifecycle})", str(e))
    
    def search_by_name_or_tags(self, query: str, limit: Optional[int] = None) -> List[AgentsCatalogueItem]:
        """Search items by name or tags using SQLAlchemy."""
        try:
            search_term = f"%{query.lower()}%"
            
            db_query = self.session.query(AgentsCatalogueItem).filter(
                or_(
                    AgentsCatalogueItem.name.ilike(search_term),
                    AgentsCatalogueItem.tags.ilike(search_term),
                    AgentsCatalogueItem.owners.ilike(search_term)
                )
            )
            db_query = db_query.order_by(AgentsCatalogueItem.created_at.desc())
            
            if limit:
                db_query = db_query.limit(limit)
            
            return db_query.all()
        except SQLAlchemyError as e:
            self.logger.error("Failed to search items with query", query=query, error=str(e))
            raise QueryExecutionError(f"search_by_name_or_tags({query})", str(e))
    
    def check_name_exists(self, name: str, exclude_id: Optional[str] = None) -> bool:
        """Check if a name already exists using SQLAlchemy."""
        try:
            query = self.session.query(AgentsCatalogueItem).filter(AgentsCatalogueItem.name == name)
            
            if exclude_id:
                query = query.filter(AgentsCatalogueItem.id != exclude_id)
            
            return query.first() is not None
        except SQLAlchemyError as e:
            self.logger.error("Failed to check name existence", name=name, error=str(e))
            raise QueryExecutionError(f"check_name_exists({name})", str(e))
    
    def get_paginated(self, offset: int, limit: int, filters: Optional[Dict[str, Any]] = None) -> List[AgentsCatalogueItem]:
        """Get paginated results with optional filters using SQLAlchemy."""
        try:
            query = self.session.query(AgentsCatalogueItem)
            
            # Apply filters
            if filters:
                if 'type' in filters:
                    query = query.filter(AgentsCatalogueItem.type == filters['type'])
                if 'lifecycle' in filters:
                    query = query.filter(AgentsCatalogueItem.lifecycle == filters['lifecycle'])
                if 'search' in filters and filters['search']:
                    search_term = f"%{filters['search'].lower()}%"
                    query = query.filter(
                        or_(
                            AgentsCatalogueItem.name.ilike(search_term),
                            AgentsCatalogueItem.tags.ilike(search_term),
                            AgentsCatalogueItem.owners.ilike(search_term)
                        )
                    )
            
            # Order by creation date (newest first)
            query = query.order_by(AgentsCatalogueItem.created_at.desc())
            
            # Apply pagination
            query = query.offset(offset).limit(limit)
            
            return query.all()
        except SQLAlchemyError as e:
            self.logger.error("Failed to get paginated items", offset=offset, limit=limit, error=str(e))
            raise QueryExecutionError(f"get_paginated({offset}, {limit})", str(e))
    
    def count_items(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count total items with optional filters using SQLAlchemy."""
        try:
            query = self.session.query(AgentsCatalogueItem)
            
            # Apply filters
            if filters:
                if 'type' in filters:
                    query = query.filter(AgentsCatalogueItem.type == filters['type'])
                if 'lifecycle' in filters:
                    query = query.filter(AgentsCatalogueItem.lifecycle == filters['lifecycle'])
                if 'search' in filters and filters['search']:
                    search_term = f"%{filters['search'].lower()}%"
                    query = query.filter(
                        or_(
                            AgentsCatalogueItem.name.ilike(search_term),
                            AgentsCatalogueItem.tags.ilike(search_term),
                            AgentsCatalogueItem.owners.ilike(search_term)
                        )
                    )
            
            return query.count()
        except SQLAlchemyError as e:
            self.logger.error("Failed to count items", error=str(e))
            raise QueryExecutionError("count_items", str(e))
    
    def create(self, item: AgentsCatalogueItem) -> AgentsCatalogueItem:
        """Override to add error handling and validation."""
        try:
            # Validate required fields
            if not item.name:
                raise ValueError("Item must have a name")
            if not item.type:
                raise ValueError("Item must have a type")
            if not item.owners:
                raise ValueError("Item must have at least one owner")
            
            # Set timestamps if not set
            import time
            current_time = int(time.time())
            if not item.created_at:
                item.created_at = current_time
            if not item.updated_at:
                item.updated_at = current_time
            
            return super().create(item)
        except SQLAlchemyError as e:
            self.logger.error("Failed to create agents catalogue item", error=str(e))
            raise TransactionError("create_agents_catalogue_item", str(e)) 