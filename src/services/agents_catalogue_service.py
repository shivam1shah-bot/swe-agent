"""
Agents Catalogue service for the SWE Agent.

Provides business logic for agents catalogue management operations.
"""

import uuid
import json
import re
import time
from typing import List, Optional, Dict, Any

from .base import BaseService
from .exceptions import ValidationError, BusinessLogicError
from src.repositories.agents_catalogue_repository import AgentsCatalogueRepository, SQLAlchemyAgentsCatalogueRepository
from src.repositories.exceptions import EntityNotFoundError, RepositoryError
from src.models.agents_catalogue_item import AgentsCatalogueItem, AgentsCatalogueItemType, LifecycleStatus
from src.providers.database.session import get_session
from src.providers.logger import Logger

class AgentsCatalogueService(BaseService):
    """Agents Catalogue service for managing agents catalogue items."""

    # Predefined tags as per requirements
    AVAILABLE_TAGS = ["INFRA", "CI", "GATEWAY_INTEGRATION", "UT", "SLIT", "E2E", "DOCS", "DE", "ONBOARDING", "FOUNDATION"]

    def __init__(self, config, database_provider):
        """Initialize the agents catalogue service."""
        super().__init__("AgentsCatalogueService")
        self._db_provider = database_provider
        self.logger = Logger("AgentsCatalogueService")
        
        # Ensure database provider is initialized first
        if database_provider and not database_provider.is_initialized():
            database_provider.initialize(config)
        
        # Force session factory reinitialization to ensure we have the right connection
        from src.providers.database.session import session_factory
        from src.providers.database.connection import get_engine
        
        try:
            # Force session factory to use the current engine
            session_factory.close()  # Close any existing factory
            session_factory.initialize()  # Reinitialize with current engine
            
            # Test the connection immediately
            with get_session() as session:
                from sqlalchemy import text
                result = session.execute(text("SELECT COUNT(*) FROM agents_catalogue_items"))
                count = result.scalar()
                self.logger.info("AgentsCatalogueService connected to database", 
                          extra={"item_count": count})

        except Exception as e:
            self.logger.error("Failed to initialize session factory", 
                              extra={"error": str(e)})
            raise

        self.initialize(config)
    
    def _get_agents_catalogue_repo(self, session):
        """Get the agents catalogue repository with a given session."""
        return SQLAlchemyAgentsCatalogueRepository(session)
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format."""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, email) is not None
    
    def _validate_owners(self, owners: List[str]) -> List[str]:
        """Validate and clean owner email addresses."""
        if not owners:
            raise ValidationError("owners", "At least one owner is required")
        
        validated_owners = []
        for owner in owners:
            if not isinstance(owner, str):
                raise ValidationError("owners", "Owner must be a string")
            
            owner = owner.strip()
            if not owner:
                continue
                
            if not self._validate_email(owner):
                raise ValidationError("owners", f"Invalid email format: {owner}")
            
            validated_owners.append(owner)
        
        if not validated_owners:
            raise ValidationError("owners", "At least one valid owner email is required")
        
        return validated_owners
    
    def _validate_item_type(self, item_type: str) -> AgentsCatalogueItemType:
        """Validate item type."""
        try:
            return AgentsCatalogueItemType(item_type)
        except ValueError:
            valid_types = [t.value for t in AgentsCatalogueItemType]
            raise ValidationError("type", f"Invalid item type '{item_type}'. Valid types: {valid_types}")
    
    def _validate_lifecycle(self, lifecycle: str) -> LifecycleStatus:
        """Validate lifecycle status."""
        try:
            return LifecycleStatus(lifecycle)
        except ValueError:
            valid_lifecycles = [s.value for s in LifecycleStatus]
            raise ValidationError("lifecycle", f"Invalid lifecycle '{lifecycle}'. Valid lifecycles: {valid_lifecycles}")
    
    def _validate_tags(self, tags: List[str]) -> List[str]:
        """Validate and clean tags."""
        if not tags:
            return []
        
        validated_tags = []
        for tag in tags:
            if not isinstance(tag, str):
                continue
                
            tag = tag.strip()
            if not tag:
                continue
                
            if tag not in self.AVAILABLE_TAGS:
                raise ValidationError("tags", f"Invalid tag '{tag}'. Available tags: {self.AVAILABLE_TAGS}")
            
            if tag not in validated_tags:
                validated_tags.append(tag)
        
        return validated_tags
    
    def create_item(
        self,
        name: str,
        description: str,
        item_type: str,
        owners: List[str],
        tags: Optional[List[str]] = None,
        lifecycle: str = "experimental"
    ) -> str:
        """
        Create a new agents catalogue item.
        
        Args:
            name: Item name (must be unique)
            description: Item description
            item_type: Type of item (api, micro-frontend)
            owners: List of owner email addresses
            tags: List of predefined tags
            lifecycle: Lifecycle status (experimental, production, deprecated)
            
        Returns:
            Created item ID
            
        Raises:
            ValidationError: If validation fails
            BusinessLogicError: If creation fails
        """
        
        try:
            # Validate inputs
            if not name or not name.strip():
                raise ValidationError("name", "Name is required")
            
            name = name.strip()
            
            # Validate type and lifecycle
            validated_type = self._validate_item_type(item_type)
            validated_lifecycle = self._validate_lifecycle(lifecycle)
            
            # Validate owners and tags
            validated_owners = self._validate_owners(owners)
            validated_tags = self._validate_tags(tags or [])
            
            with get_session() as session:
                repo = self._get_agents_catalogue_repo(session)
                
                # Check if name already exists
                if repo.check_name_exists(name):
                    raise ValidationError("name", f"An item with name '{name}' already exists")
                
                # Create the item
                item = AgentsCatalogueItem(
                    id=str(uuid.uuid4()),
                    name=name,
                    description=description or "",
                    type=validated_type,
                    lifecycle=validated_lifecycle,
                    owners=json.dumps(validated_owners),
                    tags=json.dumps(validated_tags)
                )
                
                created_item = repo.create(item)
                session.commit()
                
                self.logger.info("Created agents catalogue item", item_id=created_item.id, name=name, item_type=validated_type.value)
                return created_item.id
                
        except RepositoryError as e:
            self.logger.error("Repository error creating item", error=str(e))
            raise BusinessLogicError(f"Failed to create item: {e}")
        except Exception as e:
            self.logger.error("Unexpected error creating item", error=str(e))
            raise BusinessLogicError(f"Failed to create item: {e}")
    
    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an agents catalogue item by ID.
        
        Args:
            item_id: Item ID
            
        Returns:
            Item data as dictionary or None if not found
        """
        
        try:
            with get_session() as session:
                repo = self._get_agents_catalogue_repo(session)
                item = repo.get_by_id(item_id)
                
                if not item:
                    self.logger.warning("Item not found", item_id=item_id)
                    return None
                
                return self._item_to_dict(item)
                
        except RepositoryError as e:
            self.logger.error("Repository error getting item", item_id=item_id, error=str(e))
            raise BusinessLogicError(f"Failed to get item: {e}")
        except Exception as e:
            self.logger.error("Unexpected error getting item", item_id=item_id, error=str(e))
            raise BusinessLogicError(f"Failed to get item: {e}")
    
    def update_item(
        self,
        item_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        item_type: Optional[str] = None,
        owners: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        lifecycle: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update an agents catalogue item.
        
        Args:
            item_id: Item ID
            name: New name (optional)
            description: New description (optional)
            item_type: New item type (optional)
            owners: New owners list (optional)
            tags: New tags list (optional)
            lifecycle: New lifecycle status (optional)
            
        Returns:
            Updated item data as dictionary or None if not found
        """
        
        try:
            with get_session() as session:
                repo = self._get_agents_catalogue_repo(session)
                item = repo.get_by_id(item_id)
                
                if not item:
                    self.logger.warning("Item not found for update", item_id=item_id)
                    return None
                
                # Validate and update fields
                if name is not None:
                    name = name.strip()
                    if not name:
                        raise ValidationError("name", "Name cannot be empty")
                    
                    # Check if new name conflicts with existing items
                    if repo.check_name_exists(name, exclude_id=item_id):
                        raise ValidationError("name", f"An item with name '{name}' already exists")
                    
                    item.name = name
                
                if description is not None:
                    item.description = description
                
                if item_type is not None:
                    item.type = self._validate_item_type(item_type)
                
                if owners is not None:
                    validated_owners = self._validate_owners(owners)
                    item.owners = json.dumps(validated_owners)
                
                if tags is not None:
                    validated_tags = self._validate_tags(tags)
                    item.tags = json.dumps(validated_tags)
                
                if lifecycle is not None:
                    item.lifecycle = self._validate_lifecycle(lifecycle)
                
                # Update timestamp
                item.updated_at = int(time.time())
                
                session.commit()
                
                self.logger.info("Updated agents catalogue item", item_id=item_id)
                return self._item_to_dict(item)
                
        except RepositoryError as e:
            self.logger.error("Repository error updating item", item_id=item_id, error=str(e))
            raise BusinessLogicError(f"Failed to update item: {e}")
        except Exception as e:
            self.logger.error("Unexpected error updating item", item_id=item_id, error=str(e))
            raise BusinessLogicError(f"Failed to update item: {e}")
    
    def delete_item(self, item_id: str) -> bool:
        """
        Delete an agents catalogue item.
        
        Args:
            item_id: Item ID
            
        Returns:
            True if deleted, False if not found
        """
        
        try:
            with get_session() as session:
                repo = self._get_agents_catalogue_repo(session)
                item = repo.get_by_id(item_id)
                
                if not item:
                    self.logger.warning("Item not found for deletion", item_id=item_id)
                    return False
                
                repo.delete(item_id)
                session.commit()
                
                self.logger.info("Deleted agents catalogue item", item_id=item_id)
                return True
                
        except RepositoryError as e:
            self.logger.error("Repository error deleting item", item_id=item_id, error=str(e))
            raise BusinessLogicError(f"Failed to delete item: {e}")
        except Exception as e:
            self.logger.error("Unexpected error deleting item", item_id=item_id, error=str(e))
            raise BusinessLogicError(f"Failed to delete item: {e}")
    
    def list_items(
        self,
        page: int = 1,
        per_page: int = 20,
        search: Optional[str] = None,
        item_type: Optional[str] = None,
        lifecycle: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List agents catalogue items with pagination and filtering.
        
        Args:
            page: Page number (1-based)
            per_page: Items per page
            search: Search query for name, tags, or owners
            item_type: Filter by item type
            lifecycle: Filter by lifecycle status
            
        Returns:
            Dictionary with items, pagination info, and totals
        """
        try:
            # Validate pagination
            if page < 1:
                page = 1
            if per_page < 1 or per_page > 100:
                per_page = 20
            
            offset = (page - 1) * per_page
            
            # Build filters
            filters = {}
            
            if search:
                filters['search'] = search.strip()
            
            if item_type:
                try:
                    filters['type'] = AgentsCatalogueItemType(item_type)
                except ValueError:
                    pass  # Ignore invalid type filter
            
            if lifecycle:
                try:
                    filters['lifecycle'] = LifecycleStatus(lifecycle)
                except ValueError:
                    pass  # Ignore invalid lifecycle filter
            
            with get_session() as session:
                repo = self._get_agents_catalogue_repo(session)
                
                # Get paginated items
                items = repo.get_paginated(offset, per_page, filters)
                
                # Get total count
                total_items = repo.count_items(filters)
                
                # Calculate pagination info
                total_pages = (total_items + per_page - 1) // per_page
                has_next = page < total_pages
                has_prev = page > 1
                
                # Convert items to dictionaries
                items_dict = [self._item_to_dict(item) for item in items]
                
                return {
                    'items': items_dict,
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total_pages': total_pages,
                        'total_items': total_items,
                        'has_next': has_next,
                        'has_prev': has_prev
                    },
                    'filters': {
                        'search': search,
                        'item_type': item_type,
                        'lifecycle': lifecycle
                    }
                }
                
        except RepositoryError as e:
            self.logger.error("Repository error listing items", error=str(e))
            raise BusinessLogicError(f"Failed to list items: {e}")
        except Exception as e:
            self.logger.error("Unexpected error listing items", error=str(e))
            raise BusinessLogicError(f"Failed to list items: {e}")
    
    def get_available_types(self) -> List[str]:
        """Get available item types."""
        return [t.value for t in AgentsCatalogueItemType]
    
    def get_available_lifecycles(self) -> List[str]:
        """Get available lifecycle statuses."""
        return [s.value for s in LifecycleStatus]
    
    def get_available_tags(self) -> List[str]:
        """Get the agents catalogue configuration."""
        return self.AVAILABLE_TAGS.copy()
    
    def get_config(self) -> Dict[str, Any]:
        """Get the agents catalogue configuration."""
        return {
            'available_types': self.get_available_types(),
            'available_lifecycles': self.get_available_lifecycles(),
            'available_tags': self.get_available_tags()
        }
    
    def _item_to_dict(self, item: AgentsCatalogueItem) -> Dict[str, Any]:
        """Convert an AgentsCatalogueItem model to a dictionary."""
        
        # Safe JSON parsing with fallbacks
        def safe_json_parse(json_str, fallback=None):
            if fallback is None:
                fallback = []
            
            if not json_str or json_str.strip() == '':
                return fallback
            
            try:
                return json.loads(json_str)
            except (json.JSONDecodeError, TypeError, ValueError):
                return fallback
        
        # Safe enum value extraction - handles both enum objects and strings
        def safe_enum_value(enum_field):
            """Extract value from enum field, handling both enum objects and strings."""
            if isinstance(enum_field, str):
                return enum_field
            return enum_field.value if hasattr(enum_field, 'value') else str(enum_field)
        
        # Extract type and lifecycle values safely
        type_value = safe_enum_value(item.type)
        lifecycle_value = safe_enum_value(item.lifecycle)
        
        return {
            'id': item.id,
            'name': item.name,
            'description': item.description,
            'type': type_value,
            'type_display': type_value.replace('-', ' ').title(),
            'lifecycle': lifecycle_value,
            'owners': safe_json_parse(item.owners, []),
            'tags': safe_json_parse(item.tags, []),
            'created_at': item.created_at,
            'updated_at': item.updated_at
        } 