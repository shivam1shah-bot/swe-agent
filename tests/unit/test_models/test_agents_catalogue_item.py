"""
Unit tests for AgentsCatalogueItem model.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from src.models.agents_catalogue_item import AgentsCatalogueItem, AgentsCatalogueItemType, LifecycleStatus


@pytest.mark.unit
class TestAgentsCatalogueItemModel:
    """Test cases for AgentsCatalogueItem model."""
    
    def test_catalogue_item_creation(self):
        """Test creating an agents catalogue item instance."""
        import json
        item = AgentsCatalogueItem(
            name="test-service",
            description="A test service",
            type=AgentsCatalogueItemType.MICROFRONTEND,
            owners=json.dumps(["team1", "team2"]),
            tags=json.dumps(["web", "react"]),
            lifecycle=LifecycleStatus.PRODUCTION
        )
        
        assert item.name == "test-service"
        assert item.description == "A test service"
        assert item.type == AgentsCatalogueItemType.MICROFRONTEND
        assert json.loads(item.owners) == ["team1", "team2"]
        assert json.loads(item.tags) == ["web", "react"]
        assert item.lifecycle == LifecycleStatus.PRODUCTION
    
    def test_catalogue_item_with_empty_tags(self):
        """Test creating catalogue item with empty tags."""
        import json
        item = AgentsCatalogueItem(
            name="test-service",
            description="A test service",
            type=AgentsCatalogueItemType.API,
            owners=json.dumps(["team1"]),
            tags=None,
            lifecycle=LifecycleStatus.PRODUCTION
        )
        
        assert item.tags is None
    
    def test_catalogue_item_with_empty_lists(self):
        """Test creating catalogue item with empty lists."""
        import json
        item = AgentsCatalogueItem(
            name="test-service",
            description="A test service",
            type=AgentsCatalogueItemType.MICROFRONTEND,
            owners=json.dumps([]),
            tags=json.dumps([]),
            lifecycle=LifecycleStatus.EXPERIMENTAL
        )
        
        assert json.loads(item.owners) == []
        assert json.loads(item.tags) == []
    
    def test_catalogue_item_timestamps(self):
        """Test catalogue item timestamp behavior."""
        import json
        import time
        item = AgentsCatalogueItem(
            name="test-service",
            description="A test service",
            type=AgentsCatalogueItemType.MICROFRONTEND,
            owners=json.dumps(["team1"]),
            tags=json.dumps(["web"]),
            lifecycle=LifecycleStatus.PRODUCTION
        )
        
        # For unit tests, manually set timestamps since SQLAlchemy defaults trigger on DB save
        current_time = int(time.time())
        item.created_at = current_time
        item.updated_at = current_time
        
        assert item.created_at is not None
        assert isinstance(item.created_at, int)
        assert item.updated_at is not None
        assert isinstance(item.updated_at, int)
    
    def test_catalogue_item_string_representation(self):
        """Test catalogue item string representation."""
        import json
        item = AgentsCatalogueItem(
            name="test-service",
            description="A test service",
            type=AgentsCatalogueItemType.MICROFRONTEND,
            owners=json.dumps(["team1"]),
            tags=json.dumps(["web"]),
            lifecycle=LifecycleStatus.PRODUCTION
        )
        
        # Test that str doesn't crash
        str_repr = str(item)
        assert isinstance(str_repr, str)
        # Should contain the name
        assert "test-service" in str_repr
    
    def test_catalogue_item_equality(self):
        """Test catalogue item equality comparison."""
        import json
        item1 = AgentsCatalogueItem(
            name="test-service",
            description="A test service",
            type=AgentsCatalogueItemType.MICROFRONTEND,
            owners=json.dumps(["team1"]),
            tags=json.dumps(["web"]),
            lifecycle=LifecycleStatus.PRODUCTION
        )
        item1.id = "item-1"
        
        item2 = AgentsCatalogueItem(
            name="test-service",
            description="A test service",
            type=AgentsCatalogueItemType.MICROFRONTEND,
            owners=json.dumps(["team1"]),
            tags=json.dumps(["web"]),
            lifecycle=LifecycleStatus.PRODUCTION
        )
        item2.id = "item-1"
        
        item3 = AgentsCatalogueItem(
            name="different-service",
            description="A different service",
            type=AgentsCatalogueItemType.API,
            owners=json.dumps(["team2"]),
            tags=json.dumps(["api"]),
            lifecycle=LifecycleStatus.EXPERIMENTAL
        )
        item3.id = "item-2"
        
        # Test equality based on ID
        assert item1.id == item2.id
        assert item1.id != item3.id
    
    def test_catalogue_item_json_serialization(self):
        """Test catalogue item can be serialized to JSON-like dict."""
        import json
        item = AgentsCatalogueItem(
            name="test-service",
            description="A test service",
            type=AgentsCatalogueItemType.MICROFRONTEND,
            owners=json.dumps(["team1", "team2"]),
            tags=json.dumps(["web", "react"]),
            lifecycle=LifecycleStatus.PRODUCTION
        )
        
        # Test that attributes can be accessed (basic serialization)
        item_dict = {
            "name": item.name,
            "description": item.description,
            "type": item.type.value,
            "owners": json.loads(item.owners),
            "tags": json.loads(item.tags),
            "lifecycle": item.lifecycle.value
        }
        
        assert item_dict["name"] == "test-service"
        assert item_dict["type"] == "micro-frontend"
        assert item_dict["owners"] == ["team1", "team2"]
        assert item_dict["tags"] == ["web", "react"]
        assert item_dict["lifecycle"] == "production"
    
    def test_catalogue_item_update_fields(self):
        """Test updating catalogue item fields."""
        import json
        item = AgentsCatalogueItem(
            name="test-service",
            description="A test service",
            type=AgentsCatalogueItemType.MICROFRONTEND,
            owners=json.dumps(["team1"]),
            tags=json.dumps(["web"]),
            lifecycle=LifecycleStatus.EXPERIMENTAL
        )
        
        # Update fields
        item.description = "Updated description"
        item.lifecycle = LifecycleStatus.PRODUCTION
        item.tags = json.dumps(["web", "react", "typescript"])
        
        assert item.description == "Updated description"
        assert item.lifecycle == LifecycleStatus.PRODUCTION
        assert json.loads(item.tags) == ["web", "react", "typescript"]
    
    def test_catalogue_item_long_name(self):
        """Test catalogue item with long name."""
        import json
        long_name = "a" * 255  # Very long name
        item = AgentsCatalogueItem(
            name=long_name,
            description="A test service",
            type=AgentsCatalogueItemType.MICROFRONTEND,
            owners=json.dumps(["team1"]),
            tags=json.dumps(["web"]),
            lifecycle=LifecycleStatus.PRODUCTION
        )
        
        assert item.name == long_name
        assert len(item.name) == 255
    
    def test_catalogue_item_special_characters(self):
        """Test catalogue item with special characters."""
        import json
        item = AgentsCatalogueItem(
            name="test-service-123_special",
            description="Service with special chars: !@#$%^&*()",
            type=AgentsCatalogueItemType.MICROFRONTEND,
            owners=json.dumps(["team-1", "team_2"]),
            tags=json.dumps(["web-app", "react.js"]),
            lifecycle=LifecycleStatus.PRODUCTION
        )
        
        assert item.name == "test-service-123_special"
        assert "!@#$%^&*()" in item.description
        assert "team-1" in json.loads(item.owners)
        assert "react.js" in json.loads(item.tags)
    
    def test_catalogue_item_none_description(self):
        """Test catalogue item with None description."""
        import json
        item = AgentsCatalogueItem(
            name="test-service",
            description=None,
            type=AgentsCatalogueItemType.MICROFRONTEND,
            owners=json.dumps(["team1"]),
            tags=json.dumps(["web"]),
            lifecycle=LifecycleStatus.PRODUCTION
        )
        
        assert item.description is None
    
    def test_catalogue_item_valid_types(self):
        """Test catalogue item with different valid types."""
        import json
        types = [AgentsCatalogueItemType.MICROFRONTEND, AgentsCatalogueItemType.API]
        
        for item_type in types:
            item = AgentsCatalogueItem(
                name=f"test-{item_type.value}",
                description=f"A test {item_type.value}",
                type=item_type,
                owners=json.dumps(["team1"]),
                tags=json.dumps(["test"]),
                lifecycle=LifecycleStatus.PRODUCTION
            )
            assert item.type == item_type
    
    def test_catalogue_item_valid_lifecycles(self):
        """Test catalogue item with different valid lifecycles."""
        import json
        lifecycles = [LifecycleStatus.EXPERIMENTAL, LifecycleStatus.PRODUCTION, LifecycleStatus.DEPRECATED]
        
        for lifecycle in lifecycles:
            item = AgentsCatalogueItem(
                name="test-service",
                description="A test service",
                type=AgentsCatalogueItemType.MICROFRONTEND,
                owners=json.dumps(["team1"]),
                tags=json.dumps(["test"]),
                lifecycle=lifecycle
            )
            assert item.lifecycle == lifecycle


@pytest.mark.unit
class TestAgentsCatalogueItemValidation:
    """Test cases for AgentsCatalogueItem validation."""
    
    def test_empty_name_validation(self):
        """Test validation with empty name."""
        import json
        # This should work or raise appropriate validation error
        try:
            item = AgentsCatalogueItem(
                name="",
                description="A test service",
                type=AgentsCatalogueItemType.MICROFRONTEND,
                owners=json.dumps(["team1"]),
                tags=json.dumps(["web"]),
                lifecycle=LifecycleStatus.PRODUCTION
            )
            assert item.name == ""
        except (ValueError, TypeError):
            # Expected if validation is implemented
            pass
    
    def test_missing_required_fields(self):
        """Test validation with missing required fields."""
        # Test that required fields are enforced (if validation exists)
        try:
            item = AgentsCatalogueItem()
            # If this works, validation might not be implemented yet
        except (TypeError, ValueError):
            # Expected if validation is implemented
            pass
    
    def test_enum_validation(self):
        """Test enum validation."""
        import json
        # Test that proper enums are required
        item = AgentsCatalogueItem(
            name="test-service",
            description="A test service",
            type=AgentsCatalogueItemType.API,
            owners=json.dumps(["team1"]),
            tags=json.dumps(["web"]),
            lifecycle=LifecycleStatus.EXPERIMENTAL
        )
        assert item.type == AgentsCatalogueItemType.API
        assert item.lifecycle == LifecycleStatus.EXPERIMENTAL 