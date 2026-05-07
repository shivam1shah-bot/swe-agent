"""
Base repository interface for the SWE Agent.

Defines common repository operations and patterns.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional, Dict, Any
from sqlalchemy.orm import Session

# Generic type for entities
T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository interface.
    
    Defines common CRUD operations that all repositories should implement.
    """
    
    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[T]:
        """
        Get an entity by its ID.
        
        Args:
            entity_id: Unique identifier for the entity
            
        Returns:
            Entity instance or None if not found
        """
        pass
    
    @abstractmethod
    def get_all(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[T]:
        """
        Get all entities with optional pagination.
        
        Args:
            limit: Maximum number of entities to return
            offset: Number of entities to skip
            
        Returns:
            List of entity instances
        """
        pass
    
    @abstractmethod
    def create(self, entity: T) -> T:
        """
        Create a new entity.
        
        Args:
            entity: Entity instance to create
            
        Returns:
            Created entity instance
            
        Raises:
            DuplicateEntityError: If entity already exists
        """
        pass
    
    @abstractmethod
    def update(self, entity: T) -> T:
        """
        Update an existing entity.
        
        Args:
            entity: Entity instance to update
            
        Returns:
            Updated entity instance
            
        Raises:
            EntityNotFoundError: If entity does not exist
        """
        pass
    
    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """
        Delete an entity by its ID.
        
        Args:
            entity_id: Unique identifier for the entity
            
        Returns:
            True if entity was deleted, False if not found
        """
        pass
    
    @abstractmethod
    def exists(self, entity_id: str) -> bool:
        """
        Check if an entity exists.
        
        Args:
            entity_id: Unique identifier for the entity
            
        Returns:
            True if entity exists, False otherwise
        """
        pass
    
    @abstractmethod
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count entities with optional filters.
        
        Args:
            filters: Optional filters to apply
            
        Returns:
            Number of matching entities
        """
        pass


class SQLAlchemyBaseRepository(BaseRepository[T]):
    """
    Base SQLAlchemy repository implementation.
    
    Provides common SQLAlchemy operations for concrete repositories.
    """
    
    def __init__(self, session: Session, model_class: type):
        """
        Initialize the repository.
        
        Args:
            session: SQLAlchemy session
            model_class: SQLAlchemy model class
        """
        self.session = session
        self.model_class = model_class
    
    def get_by_id(self, entity_id: str) -> Optional[T]:
        """Get entity by ID using SQLAlchemy."""
        return self.session.query(self.model_class).filter(
            self.model_class.id == entity_id
        ).first()
    
    def get_all(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[T]:
        """Get all entities with pagination using SQLAlchemy."""
        query = self.session.query(self.model_class)
        
        if offset:
            query = query.offset(offset)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def create(self, entity: T) -> T:
        """Create entity using SQLAlchemy."""
        self.session.add(entity)
        self.session.flush()  # Flush to get ID without committing
        return entity
    
    def update(self, entity: T) -> T:
        """Update entity using SQLAlchemy."""
        self.session.merge(entity)
        self.session.flush()
        return entity
    
    def delete(self, entity_id: str) -> bool:
        """Delete entity using SQLAlchemy."""
        entity = self.get_by_id(entity_id)
        if entity:
            self.session.delete(entity)
            self.session.flush()
            return True
        return False
    
    def exists(self, entity_id: str) -> bool:
        """Check if entity exists using SQLAlchemy."""
        return self.session.query(self.model_class).filter(
            self.model_class.id == entity_id
        ).first() is not None
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities using SQLAlchemy."""
        query = self.session.query(self.model_class)
        
        if filters:
            for field, value in filters.items():
                if hasattr(self.model_class, field):
                    query = query.filter(getattr(self.model_class, field) == value)
        
        return query.count() 