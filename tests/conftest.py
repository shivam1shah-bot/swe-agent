"""
Test configuration and fixtures for SWE Agent tests.

This module provides shared test fixtures and configuration for all test modules.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Test configuration
TEST_DATA_DIR = Path(__file__).parent / "fixtures"
MOCK_GITHUB_TOKEN = "test_token_123"

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)

@pytest.fixture
def mock_github_token():
    """Mock GitHub token for testing."""
    return MOCK_GITHUB_TOKEN

@pytest.fixture
def mock_providers():
    """Mock all providers for testing."""
    providers = MagicMock()
    providers.worker = Mock()
    providers.logging = Mock()
    providers.metrics = Mock()
    providers.storage = Mock()
    providers.auth = Mock()
    providers.cache = Mock()
    return providers

@pytest.fixture
def sample_task():
    """Sample task for testing."""
    return {
        "id": "test_task_123",
        "type": "code_analysis",
        "description": "Analyze test code",
        "parameters": {
            "repository": "test/repo",
            "branch": "main"
        }
    }

@pytest.fixture
def sample_workflow():
    """Sample workflow for testing."""
    return {
        "id": "test_workflow_123",
        "name": "Test Workflow",
        "steps": [
            {"type": "analyze", "config": {}},
            {"type": "process", "config": {}},
            {"type": "output", "config": {}}
        ]
    }

@pytest.fixture
def mock_agent():
    """Mock AI agent for testing."""
    agent = Mock()
    agent.process_task.return_value = {"success": True, "result": "test_result"}
    return agent

@pytest.fixture
def test_config():
    """Test configuration settings."""
    return {
        "debug": True,
        "testing": True,
        "database_url": "sqlite:///:memory:",
        "github_token": MOCK_GITHUB_TOKEN
    }

@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Setup test environment variables."""
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", MOCK_GITHUB_TOKEN)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("APP_ENV", "test")

@pytest.fixture
def mock_database_provider():
    """Mock database provider for testing."""
    mock_provider = Mock()
    mock_provider.initialize = Mock()
    mock_provider.is_initialized = Mock(return_value=True)
    mock_provider.get_engine = Mock()
    mock_provider.health_check = Mock(return_value={"status": "healthy"})
    return mock_provider

@pytest.fixture
def mock_session():
    """Mock database session for testing."""
    mock_session = Mock()
    mock_session.query = Mock()
    mock_session.add = Mock()
    mock_session.commit = Mock()
    mock_session.rollback = Mock()
    mock_session.close = Mock()
    mock_session.__enter__ = Mock(return_value=mock_session)
    mock_session.__exit__ = Mock(return_value=None)
    return mock_session

@pytest.fixture
def mock_cache_provider():
    """Mock cache provider for testing."""
    mock_cache = Mock()
    mock_cache.get = Mock(return_value=None)
    mock_cache.set = Mock(return_value=True)
    mock_cache.delete = Mock(return_value=True)
    mock_cache.health_check = Mock(return_value={"status": "healthy"})
    return mock_cache

@pytest.fixture(autouse=True)
def mock_config_loader():
    """Mock configuration loader to prevent real config loading."""
    mock_config = {
        "app": {
            "name": "SWE Agent Test",
            "host": "localhost",
            "port": 8000,
            "debug": True
        },
        "database": {
            "type": "sqlite",
            "host": "localhost", 
            "port": 5432,
            "user": "test_user",
            "password": "test_pass",
            "name": ":memory:"
        },
        "cache": {
            "redis": {
                "host": "localhost",
                "port": 6379,
                "timeout": 1
            }
        },
        "ENVIRONMENT": "test",
        "DEBUG": True,
        "LOG_LEVEL": "DEBUG",
        "ROOT_DIR": "/tmp/test",
        "UPLOAD_FOLDER": "/tmp/test/uploads",
        "ALLOWED_EXTENSIONS": ["txt", "py"],
        "MAX_CONTENT_LENGTH": 16 * 1024 * 1024,
        "MYSQL_DB_HOST": "localhost",
        "MYSQL_DB_USER": "test_user", 
        "MYSQL_DB_PASS": "test_pass",
        "MYSQL_DB_NAME": "test_db",
        "DB_SCHEMA_VERSION": "1.0.0",
        "DEFAULT_AGENT": "test_agent"
    }
    
    with patch('src.providers.config_loader.get_config', return_value=mock_config):
        yield mock_config

@pytest.fixture(autouse=True)
def mock_database_connections():
    """Auto-mock all database connections to prevent real DB access."""
    with patch('src.providers.database.connection.get_engine') as mock_engine, \
         patch('src.providers.database.session.get_session') as mock_session_factory, \
         patch('src.migrations.manager.MigrationManager') as mock_migration_manager, \
         patch('src.providers.database.provider.DatabaseProvider.initialize') as mock_init:
        
        # Mock engine
        mock_engine.return_value = Mock()
        
        # Mock session
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)
        mock_session_factory.return_value = mock_session
        
        # Mock migration manager
        mock_migration_manager.return_value = Mock()
        
        # Mock database provider initialization
        mock_init.return_value = None
        
        yield {
            'engine': mock_engine,
            'session': mock_session_factory,
            'migration_manager': mock_migration_manager
        }

@pytest.fixture(autouse=False)  # Disable autouse to avoid import issues 
def mock_external_services():
    """Auto-mock external services to prevent real API calls."""
    # Start patches with error handling
    patches = []
    
    # Mock external modules that may not exist in test environment
    try:
        redis_patch = patch('redis.Redis')
        redis_patch.start()
        patches.append(redis_patch)
    except (ImportError, ModuleNotFoundError):
        pass
    
    try:
        redis_from_url_patch = patch('redis.from_url')
        redis_from_url_patch.start()
        patches.append(redis_from_url_patch)
    except (ImportError, ModuleNotFoundError):
        pass
    
    # Mock internal services
    with patch('src.providers.worker.sender.send_to_worker') as mock_worker, \
         patch('boto3.client') as mock_boto3:
        
        # Mock Worker
        mock_worker.return_value = True
        
        # Mock AWS SQS
        mock_sqs = Mock()
        mock_sqs.send_message = Mock(return_value={'MessageId': 'test-123'})
        mock_boto3.return_value = mock_sqs
        
        yield {
            'worker': mock_worker,
            'sqs': mock_sqs
        }
        
    # Clean up patches
    for patcher in patches:
        try:
            patcher.stop()
        except RuntimeError:
            pass

@pytest.fixture
def authenticated_client():
    """Mock authenticated FastAPI test client."""
    from fastapi.testclient import TestClient
    from src.api.api import app
    
    # Mock the authentication dependency
    def mock_get_current_user():
        return {"id": 1, "username": "testuser", "is_admin": True}
    
    # Override the dependency
    app.dependency_overrides[lambda: None] = mock_get_current_user
    
    try:
        yield TestClient(app)
    finally:
        # Clean up dependency overrides
        app.dependency_overrides.clear()

@pytest.fixture(autouse=False)  # Disable autouse to avoid import issues
def mock_fastapi_dependencies():
    """Mock FastAPI dependencies to prevent real service initialization."""
    mock_agents_service = Mock()
    mock_task_service = Mock()
    mock_db_provider = Mock()
    
    with patch('src.api.dependencies.get_agents_catalogue_service', return_value=mock_agents_service), \
         patch('src.api.dependencies.get_task_service', return_value=mock_task_service):
        yield {
            'agents_service': mock_agents_service,
            'task_service': mock_task_service,
            'db_provider': mock_db_provider
        } 

@pytest.fixture(autouse=True)
def mock_redis_completely():
    """Comprehensively mock all Redis dependencies for unit tests."""
    patches = []
    
    # Create a reusable mock Redis instance with common methods
    mock_redis_instance = Mock()
    mock_redis_instance.ping.return_value = True
    mock_redis_instance.get.return_value = None
    mock_redis_instance.set.return_value = True
    mock_redis_instance.delete.return_value = 1
    mock_redis_instance.exists.return_value = False
    mock_redis_instance.keys.return_value = []
    mock_redis_instance.flushdb.return_value = True
    mock_redis_instance.flushall.return_value = True
    mock_redis_instance.expire.return_value = True
    mock_redis_instance.ttl.return_value = -1
    mock_redis_instance.close.return_value = None
    mock_redis_instance.info.return_value = {"redis_version": "7.0.0"}
    
    # Mock the redis module itself
    try:
        redis_module_patch = patch('redis.Redis')
        mock_redis_class = redis_module_patch.start()
        mock_redis_class.return_value = mock_redis_instance
        patches.append(redis_module_patch)
    except (ImportError, ModuleNotFoundError):
        pass
    
    # Mock redis.from_url
    try:
        redis_from_url_patch = patch('redis.from_url')
        mock_from_url = redis_from_url_patch.start()
        mock_from_url.return_value = mock_redis_instance
        patches.append(redis_from_url_patch)
    except (ImportError, ModuleNotFoundError):
        pass
    
    # Mock redis.StrictRedis
    try:
        strict_redis_patch = patch('redis.StrictRedis')
        mock_strict_redis = strict_redis_patch.start()
        mock_strict_redis.return_value = mock_redis_instance
        patches.append(strict_redis_patch)
    except (ImportError, ModuleNotFoundError):
        pass
    
    # Mock our project's Redis client
    try:
        redis_client_patch = patch('src.providers.cache.redis_client.RedisClient')
        mock_client_class = redis_client_patch.start()
        mock_client_instance = Mock()
        mock_client_instance.ping.return_value = True
        mock_client_instance.get.return_value = None
        mock_client_instance.set.return_value = True
        mock_client_instance.delete.return_value = True
        mock_client_instance.exists.return_value = False
        mock_client_instance.keys.return_value = []
        mock_client_instance.close.return_value = None
        mock_client_class.return_value = mock_client_instance
        patches.append(redis_client_patch)
    except (ImportError, ModuleNotFoundError):
        pass
    
    # Mock get_redis_client function
    try:
        get_redis_patch = patch('src.providers.cache.redis_client.get_redis_client')
        mock_get_redis = get_redis_patch.start()
        mock_get_redis.return_value = mock_redis_instance
        patches.append(get_redis_patch)
    except (ImportError, ModuleNotFoundError):
        pass
    
    # Mock cache provider
    try:
        cache_provider_patch = patch('src.providers.cache.provider.CacheProvider')
        mock_cache_provider = cache_provider_patch.start()
        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache_instance.set.return_value = True
        mock_cache_instance.delete.return_value = True
        mock_cache_instance.exists.return_value = False
        mock_cache_instance.clear.return_value = True
        mock_cache_provider.return_value = mock_cache_instance
        patches.append(cache_provider_patch)
    except (ImportError, ModuleNotFoundError):
        pass
    
    # Mock cache_provider global instance
    try:
        cache_instance_patch = patch('src.providers.cache.cache_provider')
        mock_cache_instance_global = cache_instance_patch.start()
        mock_cache_instance_global.get.return_value = None
        mock_cache_instance_global.set.return_value = True
        mock_cache_instance_global.delete.return_value = True
        patches.append(cache_instance_patch)
    except (ImportError, ModuleNotFoundError):
        pass
    
    yield {
        'redis_instance': mock_redis_instance,
        'patches': patches
    }
    
    # Clean up patches
    for patcher in patches:
        try:
            patcher.stop()
        except RuntimeError:
            pass 

@pytest.fixture
def mock_fastapi_app_state():
    """Create a mock FastAPI app state with all required services for API testing."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from unittest.mock import Mock
    
    # Create mock services
    mock_config = {
        'auth': {
            'enabled': True,
            'users': {
                'dashboard': 'dashboard123',
                'admin': 'admin123'
            }
        },
        'database': {'url': 'sqlite:///:memory:'},
        'app': {'secret_key': 'test-secret'},
        'environment': {'name': 'test'}
    }
    
    mock_db_provider = Mock()
    mock_db_provider.get_session.return_value = Mock()
    mock_db_provider.close.return_value = None
    
    mock_cache_provider = Mock()
    mock_cache_provider.get.return_value = None
    mock_cache_provider.set.return_value = True
    
    mock_task_service = Mock()
    mock_task_service.get_all_tasks.return_value = []
    # create_task method removed
    
    mock_agents_catalogue_service = Mock()
    mock_agents_catalogue_service.get_all_items.return_value = []
    mock_agents_catalogue_service.create_item.return_value = Mock(id="test-item-id")
    mock_agents_catalogue_service.get_available_types.return_value = ["microfrontend", "api"]
    mock_agents_catalogue_service.get_available_lifecycles.return_value = ["experimental", "production"]
    mock_agents_catalogue_service.get_available_tags.return_value = ["INFRA", "CI"]
    
    # Add mock methods for item operations
    mock_agents_catalogue_service.update_item.return_value = {
        'id': 'test-uuid-123',
        'name': 'Updated Pipeline Generator',
        'description': 'Updated description with new features',
        'type': 'micro-frontend',
        'type_display': 'Micro Frontend',
        'lifecycle': 'production',
        'owners': ['updated.user@razorpay.com'],
        'tags': ['CI', 'INFRA'],
        'created_at': 1640995200,
        'updated_at': 1640995300
    }
    mock_agents_catalogue_service.get_item.return_value = {
        'id': 'test-uuid-123',
        'name': 'Test Item',
        'description': 'Test description',
        'type': 'micro-frontend',
        'type_display': 'Micro Frontend',
        'lifecycle': 'production',
        'owners': ['test.user@razorpay.com'],
        'tags': ['CI'],
        'created_at': 1640995200,
        'updated_at': 1640995200
    }
    mock_agents_catalogue_service.delete_item.return_value = True
    mock_agents_catalogue_service.list_items.return_value = {
        'items': [],
        'pagination': {
            'page': 1,
            'per_page': 20,
            'total_pages': 0,
            'total_items': 0,
            'has_next': False,
            'has_prev': False
        },
        'filters': {}
    }
    
    mock_cache_service = Mock()
    mock_cache_service.get.return_value = None
    mock_cache_service.set.return_value = True
    
    # Create a real FastAPI app but with mocked state
    app = FastAPI()
    
    # Add BasicAuth middleware for testing
    from src.api.middleware.basic_auth import BasicAuthMiddleware
    app.add_middleware(
        BasicAuthMiddleware,
        excluded_paths=["/health", "/docs", "/redoc", "/openapi.json"]
    )
    
    # Mock app state
    app.state.config = mock_config
    app.state.database_provider = mock_db_provider
    app.state.cache_provider = mock_cache_provider
    app.state.task_service = mock_task_service
    app.state.agents_catalogue_service = mock_agents_catalogue_service
    app.state.cache_service = mock_cache_service
    
    return app

@pytest.fixture
def authenticated_api_client(mock_fastapi_app_state):
    """Create an authenticated test client for API testing."""
    from fastapi.testclient import TestClient
    from unittest.mock import patch
    import base64
    
    # Use credentials from default.toml config
    # admin:admin123 (this matches the default configuration)
    auth_credentials = base64.b64encode(b"admin:admin123").decode('ascii')
    
    # CRITICAL: Patch config BEFORE creating any auth-related objects
    with patch('src.providers.config_loader.get_config') as mock_get_config:
        # Mock config to include authentication settings
        mock_get_config.return_value = {
            'auth': {
                'enabled': True,
                'users': {
                    'dashboard': 'dashboard123',
                    'admin': 'admin123'
                }
            },
            'database': {'url': 'sqlite:///:memory:'},
            'app': {'secret_key': 'test-secret'},
            'environment': {'name': 'test'},
            'cache': {'redis': {'host': 'localhost', 'port': 6379}},
            'aws': {'region': 'us-west-2'},
            'github': {'api_url': 'https://api.github.com', 'token': 'test'},
            'worker': {'max_retries': 3}
        }
        
        # Mock database and external dependencies but allow real auth
        with patch('src.providers.database.connection.get_engine', return_value=Mock()), \
             patch('src.providers.database.session.get_session', return_value=Mock()), \
             patch('src.providers.database.session.session_factory') as mock_session_factory, \
             patch('src.migrations.manager.MigrationManager') as mock_migration_manager:
            
            # Mock session factory
            mock_session = Mock()
            mock_session_factory.create_session.return_value = mock_session
            mock_session_factory.initialize.return_value = None
            
            # Mock migration manager
            mock_migration_instance = Mock()
            # Migration-related methods removed
            mock_migration_instance.rollback_to_version.return_value = {
                'success': True,
                'target_version': '002'
            }
            mock_migration_manager.return_value = mock_migration_instance
            
            # Add routes to the app
            from src.api.routers import admin, agents_catalogue, tasks, health
            mock_fastapi_app_state.include_router(admin.router, prefix="/admin", tags=["admin"])
            mock_fastapi_app_state.include_router(agents_catalogue.router, prefix="/agents-catalogue", tags=["agents-catalogue"])
            mock_fastapi_app_state.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
            mock_fastapi_app_state.include_router(health.router, prefix="/health", tags=["health"])
            
            # Override dependencies to inject mocked services
            from src.api.dependencies import (
                get_task_service, get_agents_catalogue_service, 
                get_cache_service, get_logger, get_db_session
            )
            
            def mock_get_task_service():
                return mock_fastapi_app_state.state.task_service
                
            def mock_get_agents_catalogue_service():
                return mock_fastapi_app_state.state.agents_catalogue_service
                
            def mock_get_cache_service():
                return mock_fastapi_app_state.state.cache_service
                
            def mock_get_logger():
                return Mock()
                
            def mock_get_db_session():
                return Mock()
            
            mock_fastapi_app_state.dependency_overrides[get_task_service] = mock_get_task_service
            mock_fastapi_app_state.dependency_overrides[get_agents_catalogue_service] = mock_get_agents_catalogue_service
            mock_fastapi_app_state.dependency_overrides[get_cache_service] = mock_get_cache_service
            mock_fastapi_app_state.dependency_overrides[get_logger] = mock_get_logger
            mock_fastapi_app_state.dependency_overrides[get_db_session] = mock_get_db_session
            
            # Mock the require_role decorator to always allow access
            def mock_require_role(allowed_roles, method_specific=None):
                def decorator(func):
                    return func  # Just return the original function without auth check
                return decorator
            
            with patch('src.providers.auth.rbac.require_role', mock_require_role):
                client = TestClient(mock_fastapi_app_state)
                
                # Set authentication header with admin credentials
                client.headers.update({"Authorization": f"Basic {auth_credentials}"})
                
                yield client
            
            # Clean up dependency overrides
            mock_fastapi_app_state.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def mock_database_for_api():
    """Mock database initialization for API tests."""
    with patch('src.providers.database.connection.initialize_engine') as mock_init, \
         patch('src.providers.database.connection.get_engine') as mock_get_engine, \
         patch('src.providers.database.session.session_factory') as mock_session_factory, \
         patch('src.providers.database.provider.DatabaseProvider.initialize') as mock_db_init:
        
        # Mock engine
        mock_engine = Mock()
        mock_init.return_value = mock_engine
        mock_get_engine.return_value = mock_engine
        
        # Mock session factory
        mock_session = Mock()
        mock_session_factory.create_session.return_value = mock_session
        mock_session_factory.initialize.return_value = None
        
        # Mock database provider initialization
        mock_db_init.return_value = None
        
        yield {
            'engine': mock_engine,
            'session': mock_session,
            'session_factory': mock_session_factory
        } 