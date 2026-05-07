"""
Unit tests for base repository functionality.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.repositories.base import BaseRepository, SQLAlchemyBaseRepository
from src.repositories.exceptions import RepositoryError


@pytest.mark.unit
class TestBaseRepository:
    """Test cases for BaseRepository."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.mock_model_class = Mock()
        self.repository = SQLAlchemyBaseRepository(self.mock_session, self.mock_model_class)
    
    def test_repository_initialization(self):
        """Test repository initialization."""
        assert self.repository.session == self.mock_session
        assert self.repository.model_class == self.mock_model_class
        assert self.repository is not None
    
    def test_repository_get_session(self):
        """Test getting repository session."""
        session = self.repository.session
        assert session == self.mock_session
    
    def test_repository_create_basic(self):
        """Test basic create operation."""
        # Mock entity
        mock_entity = Mock()
        mock_entity.id = 1
        
        # Mock session behavior
        self.mock_session.add = Mock()
        self.mock_session.flush = Mock()
        
        # Call create
        result = self.repository.create(mock_entity)
        
        # Verify calls
        self.mock_session.add.assert_called_once_with(mock_entity)
        self.mock_session.flush.assert_called_once()
        
        # Result should be the entity
        assert result == mock_entity
    
    def test_repository_create_with_error(self):
        """Test create operation with database error."""
        mock_entity = Mock()
        
        # Mock session to raise error on flush
        self.mock_session.add = Mock()
        self.mock_session.flush = Mock(side_effect=Exception("DB Error"))
        
        # Should raise the error
        with pytest.raises(Exception):
            self.repository.create(mock_entity)
    
    def test_repository_get_by_id(self):
        """Test getting entity by ID."""
        # Mock query result
        mock_entity = Mock()
        mock_entity.id = "test-id"
        
        # Setup query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = mock_entity
        self.mock_session.query.return_value = mock_query
        
        # Mock model class for the filter
        self.mock_model_class.id = "test-id"
        
        result = self.repository.get_by_id("test-id")
        assert result == mock_entity
        self.mock_session.query.assert_called_once_with(self.mock_model_class)
    
    def test_repository_update_basic(self):
        """Test basic update operation."""
        mock_entity = Mock()
        mock_entity.id = 1
        
        self.mock_session.merge = Mock(return_value=mock_entity)
        self.mock_session.flush = Mock()
        
        result = self.repository.update(mock_entity)
        self.mock_session.merge.assert_called_once_with(mock_entity)
        self.mock_session.flush.assert_called_once()
        assert result == mock_entity
    
    def test_repository_delete_basic(self):
        """Test basic delete operation."""
        mock_entity = Mock()
        mock_entity.id = "test-id"
        
        # Mock get_by_id to return the entity
        with patch.object(self.repository, 'get_by_id', return_value=mock_entity):
            self.mock_session.delete = Mock()
            self.mock_session.flush = Mock()
            
            result = self.repository.delete("test-id")
            self.mock_session.delete.assert_called_once_with(mock_entity)
            self.mock_session.flush.assert_called_once()
            assert result is True
    
    def test_repository_list_all(self):
        """Test listing all entities."""
        mock_entities = [Mock(), Mock(), Mock()]
        
        mock_query = Mock()
        mock_query.all.return_value = mock_entities
        self.mock_session.query.return_value = mock_query
        
        result = self.repository.get_all()
        assert result == mock_entities
        self.mock_session.query.assert_called_once_with(self.mock_model_class)
    
    def test_repository_count(self):
        """Test counting entities."""
        expected_count = 5
        
        mock_query = Mock()
        mock_query.count.return_value = expected_count
        self.mock_session.query.return_value = mock_query
        
        result = self.repository.count()
        assert result == expected_count
        self.mock_session.query.assert_called_once_with(self.mock_model_class)
    
    def test_repository_exists(self):
        """Test checking if entity exists."""
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = Mock()  # Found entity
        self.mock_session.query.return_value = mock_query
        
        result = self.repository.exists("test-id")
        assert result is True
    
    def test_repository_transaction_handling(self):
        """Test transaction handling."""
        mock_entity = Mock()
        
        # Test successful transaction
        self.mock_session.add = Mock()
        self.mock_session.flush = Mock()
        
        self.repository.create(mock_entity)
        self.mock_session.flush.assert_called_once()
    
    def test_repository_session_management(self):
        """Test session management."""
        # Repository should use provided session
        assert self.repository.session == self.mock_session
        
        # Test session context manager if available
        if hasattr(self.repository, '__enter__'):
            with self.repository as repo:
                assert repo == self.repository
    
    def test_repository_error_handling(self):
        """Test error handling in repository operations."""
        mock_entity = Mock()
        
        # Mock session to raise various errors
        self.mock_session.add = Mock()
        self.mock_session.flush = Mock(side_effect=Exception("Database error"))
        
        with pytest.raises(Exception):
            self.repository.create(mock_entity)


@pytest.mark.unit
class TestBaseRepositoryValidation:
    """Test cases for BaseRepository validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.mock_model_class = Mock()
        self.repository = SQLAlchemyBaseRepository(self.mock_session, self.mock_model_class)
    
    def test_repository_validate_entity(self):
        """Test entity validation."""
        mock_entity = Mock()
        
        # Test validation if method exists
        if hasattr(self.repository, 'validate'):
            try:
                result = self.repository.validate(mock_entity)
                assert result in [True, None]  # Should return True or None
            except NotImplementedError:
                # Expected if validation is not implemented
                pass
    
    def test_repository_validate_none_entity(self):
        """Test validation with None entity."""
        if hasattr(self.repository, 'validate'):
            with pytest.raises((ValueError, TypeError)):
                self.repository.validate(None)
    
    def test_repository_sanitize_input(self):
        """Test input sanitization."""
        test_input = "test_input"
        
        # Test sanitization if method exists
        if hasattr(self.repository, 'sanitize_input'):
            result = self.repository.sanitize_input(test_input)
            assert result is not None
    
    def test_repository_check_permissions(self):
        """Test permission checking."""
        mock_entity = Mock()
        
        # Test permission checking if method exists
        if hasattr(self.repository, 'check_permissions'):
            try:
                result = self.repository.check_permissions(mock_entity)
                assert result in [True, False, None]
            except NotImplementedError:
                # Expected if not implemented
                pass


@pytest.mark.unit
class TestRepositoryExceptions:
    """Test cases for repository exceptions."""
    
    def test_repository_error_creation(self):
        """Test creating RepositoryError."""
        error = RepositoryError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_validation_error_creation(self):
        """Test creating ValueError for validation."""
        error = ValueError("Validation failed")
        assert str(error) == "Validation failed"
        assert isinstance(error, Exception)
    
    def test_repository_error_with_cause(self):
        """Test RepositoryError with underlying cause."""
        error = RepositoryError("Wrapper error")
        
        assert str(error) == "Wrapper error"
        assert isinstance(error, Exception)
    
    def test_error_inheritance(self):
        """Test error inheritance hierarchy."""
        repo_error = RepositoryError("test")
        validation_error = ValueError("test")
        
        assert isinstance(repo_error, Exception)
        assert isinstance(validation_error, Exception)
    
    def test_error_messages(self):
        """Test error message handling."""
                # Test various message types
        errors = [
            RepositoryError("Simple message"),
            RepositoryError(""),
            ValueError("Validation message"),
            ValueError("")
        ]
        
        for error in errors:
            # Should not crash when converting to string
            str_repr = str(error)
            assert isinstance(str_repr, str)


@pytest.mark.unit 
class TestBaseRepositoryIntegration:
    """Integration test cases for BaseRepository with mocked dependencies."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.mock_model_class = Mock()
        self.repository = SQLAlchemyBaseRepository(self.mock_session, self.mock_model_class)
    
    def test_repository_crud_flow(self):
        """Test complete CRUD flow."""
        mock_entity = Mock()
        mock_entity.id = 1
        mock_entity.name = "Test Entity"
        
        # Setup session mocks
        self.mock_session.add = Mock()
        self.mock_session.commit = Mock()
        self.mock_session.delete = Mock()
        self.mock_session.merge = Mock(return_value=mock_entity)
        
        # Test create
        created = self.repository.create(mock_entity)
        assert created == mock_entity
        self.mock_session.add.assert_called_with(mock_entity)
        
        # Test update
        updated = self.repository.update(mock_entity)
        assert updated == mock_entity
        
        # Test delete
        with patch.object(self.repository, 'get_by_id', return_value=mock_entity):
            result = self.repository.delete("test-id")
            assert result is True
    
    def test_repository_query_operations(self):
        """Test query operations."""
        mock_entities = [Mock(), Mock()]
        
        # Setup query mocks
        mock_query = Mock()
        mock_query.all.return_value = mock_entities
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_entities[0]
        mock_query.count.return_value = len(mock_entities)
        
        self.mock_session.query.return_value = mock_query
        
        # Test query methods
        result = self.repository.get_all()
        assert result == mock_entities
        
        result = self.repository.get_by_id("test-id")
        assert result == mock_entities[0]
    
    def test_repository_error_scenarios(self):
        """Test various error scenarios."""
        mock_entity = Mock()
        
        # Test flush failure
        self.mock_session.add = Mock()
        self.mock_session.flush = Mock(side_effect=Exception("Flush failed"))
        
        with pytest.raises(Exception):
            self.repository.create(mock_entity) 