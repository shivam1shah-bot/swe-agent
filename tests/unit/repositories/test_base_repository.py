"""
Unit tests for Base Repository classes.

Tests both the abstract BaseRepository interface and SQLAlchemyBaseRepository implementation.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer

from src.repositories.base import BaseRepository, SQLAlchemyBaseRepository


# Create a test model for SQLAlchemy tests
Base = declarative_base()


class TestModel(Base):
    """Test SQLAlchemy model."""
    __tablename__ = 'test_table'

    id = Column(String, primary_key=True)
    name = Column(String)
    value = Column(Integer)


class TestBaseRepository:
    """Test suite for BaseRepository abstract class."""

    def test_base_repository_is_abstract(self):
        """Test that BaseRepository cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseRepository()

    def test_base_repository_requires_methods(self):
        """Test that subclasses must implement all abstract methods."""

        # Create incomplete subclass
        class IncompleteRepository(BaseRepository):
            pass

        with pytest.raises(TypeError):
            IncompleteRepository()

    def test_base_repository_can_be_subclassed(self):
        """Test that BaseRepository can be properly subclassed."""

        class CompleteRepository(BaseRepository):
            def get_by_id(self, entity_id: str):
                return None

            def get_all(self, limit=None, offset=None):
                return []

            def create(self, entity):
                return entity

            def update(self, entity):
                return entity

            def delete(self, entity_id: str):
                return False

            def exists(self, entity_id: str):
                return False

            def count(self, filters=None):
                return 0

        # Should be able to instantiate
        repo = CompleteRepository()
        assert isinstance(repo, BaseRepository)


class TestSQLAlchemyBaseRepository:
    """Test suite for SQLAlchemyBaseRepository implementation."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock SQLAlchemy session."""
        session = Mock(spec=Session)
        return session

    @pytest.fixture
    def repository(self, mock_session):
        """Create a SQLAlchemyBaseRepository instance."""
        return SQLAlchemyBaseRepository(mock_session, TestModel)

    def test_init(self, mock_session):
        """Test repository initialization."""
        repo = SQLAlchemyBaseRepository(mock_session, TestModel)

        assert repo.session == mock_session
        assert repo.model_class == TestModel

    def test_get_by_id_found(self, repository, mock_session):
        """Test getting entity by ID when it exists."""
        mock_entity = TestModel(id="123", name="Test", value=42)
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_entity

        mock_session.query.return_value = mock_query

        result = repository.get_by_id("123")

        assert result == mock_entity
        mock_session.query.assert_called_once_with(TestModel)

    def test_get_by_id_not_found(self, repository, mock_session):
        """Test getting entity by ID when it doesn't exist."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None

        mock_session.query.return_value = mock_query

        result = repository.get_by_id("999")

        assert result is None

    def test_get_all_no_pagination(self, repository, mock_session):
        """Test getting all entities without pagination."""
        mock_entities = [
            TestModel(id="1", name="Test1", value=1),
            TestModel(id="2", name="Test2", value=2)
        ]
        mock_query = Mock()
        mock_query.all.return_value = mock_entities

        mock_session.query.return_value = mock_query

        result = repository.get_all()

        assert result == mock_entities
        mock_session.query.assert_called_once_with(TestModel)

    def test_get_all_with_limit(self, repository, mock_session):
        """Test getting all entities with limit."""
        mock_entities = [TestModel(id="1", name="Test1", value=1)]
        mock_query = Mock()
        mock_query.limit.return_value.all.return_value = mock_entities

        mock_session.query.return_value = mock_query

        result = repository.get_all(limit=10)

        assert result == mock_entities
        mock_query.limit.assert_called_once_with(10)

    def test_get_all_with_offset(self, repository, mock_session):
        """Test getting all entities with offset."""
        mock_entities = [TestModel(id="1", name="Test1", value=1)]
        mock_query = Mock()
        mock_query.offset.return_value.all.return_value = mock_entities

        mock_session.query.return_value = mock_query

        result = repository.get_all(offset=5)

        assert result == mock_entities
        mock_query.offset.assert_called_once_with(5)

    def test_get_all_with_limit_and_offset(self, repository, mock_session):
        """Test getting all entities with both limit and offset."""
        mock_entities = [TestModel(id="1", name="Test1", value=1)]
        mock_query = Mock()
        mock_query.offset.return_value.limit.return_value.all.return_value = mock_entities

        mock_session.query.return_value = mock_query

        result = repository.get_all(limit=10, offset=5)

        assert result == mock_entities
        mock_query.offset.assert_called_once_with(5)
        mock_query.offset.return_value.limit.assert_called_once_with(10)

    def test_create(self, repository, mock_session):
        """Test creating a new entity."""
        entity = TestModel(id="123", name="Test", value=42)

        result = repository.create(entity)

        assert result == entity
        mock_session.add.assert_called_once_with(entity)
        mock_session.flush.assert_called_once()

    def test_update(self, repository, mock_session):
        """Test updating an existing entity."""
        entity = TestModel(id="123", name="Updated", value=99)

        result = repository.update(entity)

        assert result == entity
        mock_session.merge.assert_called_once_with(entity)
        mock_session.flush.assert_called_once()

    def test_delete_existing_entity(self, repository, mock_session):
        """Test deleting an existing entity."""
        mock_entity = TestModel(id="123", name="Test", value=42)
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_entity

        mock_session.query.return_value = mock_query

        result = repository.delete("123")

        assert result is True
        mock_session.delete.assert_called_once_with(mock_entity)
        mock_session.flush.assert_called_once()

    def test_delete_non_existing_entity(self, repository, mock_session):
        """Test deleting a non-existing entity."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None

        mock_session.query.return_value = mock_query

        result = repository.delete("999")

        assert result is False
        mock_session.delete.assert_not_called()
        mock_session.flush.assert_not_called()

    def test_exists_true(self, repository, mock_session):
        """Test checking if entity exists when it does."""
        mock_entity = TestModel(id="123", name="Test", value=42)
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_entity

        mock_session.query.return_value = mock_query

        result = repository.exists("123")

        assert result is True

    def test_exists_false(self, repository, mock_session):
        """Test checking if entity exists when it doesn't."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None

        mock_session.query.return_value = mock_query

        result = repository.exists("999")

        assert result is False

    def test_count_no_filters(self, repository, mock_session):
        """Test counting entities without filters."""
        mock_query = Mock()
        mock_query.count.return_value = 42

        mock_session.query.return_value = mock_query

        result = repository.count()

        assert result == 42
        mock_session.query.assert_called_once_with(TestModel)

    def test_count_with_filters(self, repository, mock_session):
        """Test counting entities with filters."""
        mock_query = Mock()
        # For chained filter calls, each filter() should return the query itself
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 5

        mock_session.query.return_value = mock_query

        filters = {"name": "Test", "value": 42}
        result = repository.count(filters)

        assert result == 5
        # Should have been called twice (once for each filter)
        assert mock_query.filter.call_count == 2

    def test_count_with_invalid_filter_field(self, repository, mock_session):
        """Test counting with filter for non-existent field."""
        mock_query = Mock()
        mock_query.count.return_value = 42

        mock_session.query.return_value = mock_query

        # Filter with field that doesn't exist on model
        filters = {"nonexistent_field": "value"}
        result = repository.count(filters)

        # Should still work but filter shouldn't be applied
        assert result == 42
        mock_query.filter.assert_not_called()

    def test_count_empty_filters(self, repository, mock_session):
        """Test counting with empty filters dict."""
        mock_query = Mock()
        mock_query.count.return_value = 42

        mock_session.query.return_value = mock_query

        result = repository.count(filters={})

        assert result == 42
        mock_query.filter.assert_not_called()

    def test_session_management(self, mock_session):
        """Test that repository doesn't commit session automatically."""
        repo = SQLAlchemyBaseRepository(mock_session, TestModel)
        entity = TestModel(id="123", name="Test", value=42)

        # Create entity
        repo.create(entity)

        # flush should be called, but not commit
        mock_session.flush.assert_called()
        mock_session.commit.assert_not_called()

    def test_generic_type_support(self, mock_session):
        """Test that repository supports generic type hints."""
        repo = SQLAlchemyBaseRepository(mock_session, TestModel)

        # Repository should work with the specified model type
        assert repo.model_class == TestModel

    def test_multiple_repositories_independent(self):
        """Test that multiple repository instances are independent."""
        session1 = Mock(spec=Session)
        session2 = Mock(spec=Session)

        repo1 = SQLAlchemyBaseRepository(session1, TestModel)
        repo2 = SQLAlchemyBaseRepository(session2, TestModel)

        # Each should have its own session
        assert repo1.session != repo2.session
        assert repo1.session == session1
        assert repo2.session == session2

    def test_repository_inherits_from_base(self, repository):
        """Test that SQLAlchemyBaseRepository inherits from BaseRepository."""
        assert isinstance(repository, BaseRepository)

    def test_get_by_id_uses_model_id_attribute(self, repository, mock_session):
        """Test that get_by_id uses the model's id attribute."""
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter

        mock_session.query.return_value = mock_query

        repository.get_by_id("123")

        # Verify filter was called (checking exact filter expression is tricky)
        mock_query.filter.assert_called_once()

    def test_all_methods_use_flush_not_commit(self, repository, mock_session):
        """Test that all modification methods use flush, not commit."""
        entity = TestModel(id="123", name="Test", value=42)

        # Test create
        repository.create(entity)
        mock_session.flush.assert_called()
        mock_session.commit.assert_not_called()
        mock_session.flush.reset_mock()

        # Test update
        repository.update(entity)
        mock_session.flush.assert_called()
        mock_session.commit.assert_not_called()
        mock_session.flush.reset_mock()

        # Test delete
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = entity
        mock_session.query.return_value = mock_query

        repository.delete("123")
        mock_session.flush.assert_called()
        mock_session.commit.assert_not_called()
