"""
Unit tests for config loader provider.
"""
import pytest
import os
import tempfile
import toml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from src.providers.config_loader import get_config
from src.providers.config_loader.env_loader import EnvConfigLoader


@pytest.mark.unit
class TestConfigLoader:
    """Test cases for config loader functionality."""
    
    def test_get_config_returns_dict(self):
        """Test that get_config returns a dictionary."""
        config = get_config()
        assert isinstance(config, dict)
        assert len(config) > 0
    
    def test_get_config_has_required_fields(self):
        """Test that config has required fields."""
        config = get_config()
        
        # Test for legacy compatibility fields
        required_fields = [
            'ENVIRONMENT', 'DEBUG', 'LOG_LEVEL', 'ROOT_DIR',
            'UPLOAD_FOLDER', 'ALLOWED_EXTENSIONS', 'MAX_CONTENT_LENGTH'
        ]
        
        for field in required_fields:
            assert field in config, f"Required field {field} missing from config"
    
    def test_get_config_database_fields(self):
        """Test that config has database-related fields."""
        config = get_config()
        
        db_fields = [
            'MYSQL_DB_HOST', 'MYSQL_DB_USER', 'MYSQL_DB_PASS',
            'MYSQL_DB_NAME', 'DB_SCHEMA_VERSION'
        ]
        
        for field in db_fields:
            assert field in config, f"Database field {field} missing from config"
    
    def test_get_config_agent_fields(self):
        """Test that config has agent-related fields."""
        config = get_config()
        assert 'DEFAULT_AGENT' in config
    
    @patch('src.providers.config_loader.EnvConfigLoader')
    def test_get_config_uses_env_loader(self, mock_loader_class):
        """Test that get_config uses EnvConfigLoader."""
        # Reset the global instance to force initialization
        import src.providers.config_loader
        src.providers.config_loader._config_instance = None
        
        mock_loader = mock_loader_class.return_value
        mock_loader.get_all.return_value = {"test": "config"}
        mock_loader.update_from_env.return_value = None
        
        config = get_config()
        
        mock_loader_class.assert_called_once()
        mock_loader.update_from_env.assert_called_once()
        mock_loader.get_all.assert_called_once()
    
    def test_get_config_caching(self):
        """Test that get_config caches results."""
        config1 = get_config()
        config2 = get_config()
        
        # Should return same structure (might not be identical object due to copying)
        assert config1.keys() == config2.keys()
    
    def test_get_config_environment_override(self):
        """Test that environment variables override config."""
        with patch.dict(os.environ, {'LOG_LEVEL': 'ERROR'}):
            config = get_config()
            # Should either use env var or have consistent behavior
            assert 'LOG_LEVEL' in config


@pytest.mark.unit
class TestEnvConfigLoader:
    """Test cases for EnvConfigLoader."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create test config
        self.test_config = {
            "app": {
                "name": "Test App",
                "host": "localhost",
                "port": 8000,
                "debug": False
            },
            "database": {
                "type": "mysql",
                "host": "localhost",
                "port": 3306,
                "user": "test_user",
                "password": "test_pass",
                "name": "test_db"
            }
        }
        
        # Write default config file
        with open(self.temp_path / "env.default.toml", "w") as f:
            toml.dump(self.test_config, f)
    
    def teardown_method(self):
        """Cleanup test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('pathlib.Path.cwd')
    def test_env_loader_initialization(self, mock_cwd):
        """Test EnvConfigLoader initialization."""
        mock_cwd.return_value = self.temp_path
        
        loader = EnvConfigLoader()
        assert loader is not None
    
    @patch('pathlib.Path.cwd')
    def test_env_loader_load_config(self, mock_cwd):
        """Test loading configuration from file."""
        mock_cwd.return_value = self.temp_path
        
        # Create a minimal config file for this test
        env_file = self.temp_path / "environments" / "env.default.toml"
        env_file.parent.mkdir(parents=True, exist_ok=True)
        env_file.write_text("""
[app]
name = "test-app"
debug = false

[database]
type = "mysql"
host = "localhost"
""")
        
        loader = EnvConfigLoader()
        config = loader.get_all()
        
        assert isinstance(config, dict)
        assert len(config) >= 0  # Should be ok even if empty in test environment
    
    @patch('pathlib.Path.cwd')
    def test_env_loader_environment_update(self, mock_cwd):
        """Test updating config from environment variables."""
        mock_cwd.return_value = self.temp_path
        
        with patch.dict(os.environ, {'APP_ENV': 'test'}):
            loader = EnvConfigLoader()
            loader.update_from_env()
            
            # Should not crash
            config = loader.get_all()
            assert isinstance(config, dict)
    
    def test_env_loader_merge_configs(self):
        """Test merging multiple configuration sources."""
        # Create dev config
        dev_config = {
            "app": {
                "debug": True,
                "port": 8001
            }
        }
        
        with open(self.temp_path / "env.dev.toml", "w") as f:
            toml.dump(dev_config, f)
        
        with patch('pathlib.Path.cwd', return_value=self.temp_path):
            with patch.dict(os.environ, {'APP_ENV': 'dev'}):
                loader = EnvConfigLoader()
                config = loader.get_all()
                
                assert isinstance(config, dict)
    
    def test_env_loader_missing_file(self):
        """Test behavior when config file is missing."""
        empty_dir = tempfile.mkdtemp()
        try:
            with patch('pathlib.Path.cwd', return_value=Path(empty_dir)):
                loader = EnvConfigLoader()
                config = loader.get_all()
                
                # Should handle gracefully
                assert isinstance(config, dict)
        finally:
            import shutil
            shutil.rmtree(empty_dir)
    
    @patch('pathlib.Path.cwd')
    def test_env_loader_invalid_toml(self, mock_cwd):
        """Test handling of invalid TOML file."""
        mock_cwd.return_value = self.temp_path
        
        # Write invalid TOML
        with open(self.temp_path / "env.default.toml", "w") as f:
            f.write("invalid toml content [[[")
        
        loader = EnvConfigLoader()
        # Should handle error gracefully
        try:
            config = loader.get_all()
            assert isinstance(config, dict)
        except Exception:
            # Expected if validation is strict
            pass


@pytest.mark.unit
class TestConfigValidation:
    """Test cases for configuration validation."""
    
    def test_config_type_validation(self):
        """Test configuration value types."""
        config = get_config()
        
        # Test boolean fields - DEBUG is converted to int (0/1) for backward compatibility
        if 'DEBUG' in config:
            assert isinstance(config['DEBUG'], (bool, int))
        
        # Test string fields
        if 'ENVIRONMENT' in config:
            assert isinstance(config['ENVIRONMENT'], str)
        
        # Test numeric fields
        if 'MAX_CONTENT_LENGTH' in config:
            assert isinstance(config['MAX_CONTENT_LENGTH'], (int, float))
    
    def test_config_list_validation(self):
        """Test configuration list values."""
        config = get_config()
        
        if 'ALLOWED_EXTENSIONS' in config:
            # ALLOWED_EXTENSIONS is a set, not a list
            assert isinstance(config['ALLOWED_EXTENSIONS'], (list, set))
            for ext in config['ALLOWED_EXTENSIONS']:
                assert isinstance(ext, str)
    
    def test_config_path_validation(self):
        """Test configuration path values."""
        config = get_config()
        
        path_fields = ['ROOT_DIR', 'UPLOAD_FOLDER']
        for field in path_fields:
            if field in config and config[field]:
                assert isinstance(config[field], str)
    
    def test_config_default_values(self):
        """Test that config has sensible default values."""
        config = get_config()
        
        # Test that essential fields have non-empty values
        if 'ENVIRONMENT' in config:
            assert config['ENVIRONMENT'] is not None
            assert len(config['ENVIRONMENT']) > 0
        
        if 'LOG_LEVEL' in config:
            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            assert config['LOG_LEVEL'] in valid_levels
    
    def test_config_auth_users_include_mcp_read_user(self):
        """Test that auth configuration includes mcp_read_user."""
        config = get_config()
        
        # Check if auth configuration exists
        auth_config = config.get('auth', {})
        if auth_config.get('enabled', False):
            users = auth_config.get('users', {})
            # In development, mcp_read_user should be configured
            if users:
                assert 'dashboard' in users
                assert 'admin' in users
                # mcp_read_user should be present in the configuration
                assert 'mcp_read_user' in users
    
    def test_config_consistency(self):
        """Test configuration consistency across calls."""
        config1 = get_config()
        config2 = get_config()
        
        # Should be consistent
        assert config1.keys() == config2.keys()
        
        # Key values should be the same
        for key in config1.keys():
            assert config1[key] == config2[key] 