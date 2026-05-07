"""
Tests for the EnvConfigLoader functionality.
"""

import os
import tempfile
import toml
from pathlib import Path
from unittest.mock import patch

import pytest

from src.providers.config_loader.env_loader import EnvConfigLoader


class TestEnvConfigLoader:
    """Test cases for EnvConfigLoader."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create default config
        self.default_config = {
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
            },
            "cache": {
                "redis": {
                    "host": "localhost",
                    "port": 6379,
                    "timeout": 1
                }
            }
        }
        
        # Create dev config with overrides
        self.dev_config = {
            "app": {
                "debug": True,
                "port": 8001
            },
            "database": {
                "user": "dev_user",
                "password": "dev_pass"
            }
        }
        
        # Write default config file
        with open(self.temp_path / "env.default.toml", "w") as f:
            toml.dump(self.default_config, f)
            
        # Write dev config file
        with open(self.temp_path / "env.dev.toml", "w") as f:
            toml.dump(self.dev_config, f)
    
    def teardown_method(self):
        """Cleanup test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_load_default_config(self):
        """Test loading default configuration."""
        loader = EnvConfigLoader(env_name="nonexistent", root_dir=self.temp_dir)
        
        # Should load default config
        assert loader.get("app.name") == "Test App"
        assert loader.get("app.host") == "localhost"
        assert loader.get("app.port") == 8000
        assert loader.get("app.debug") is False
        
        # Should load database config
        assert loader.get("database.type") == "mysql"
        assert loader.get("database.host") == "localhost"
        assert loader.get("database.user") == "test_user"
        
        # Should load nested cache config
        assert loader.get("cache.redis.host") == "localhost"
        assert loader.get("cache.redis.port") == 6379
    
    def test_load_dev_config_with_overrides(self):
        """Test loading dev configuration with overrides."""
        loader = EnvConfigLoader(env_name="dev", root_dir=self.temp_dir)
        
        # Should override app config
        assert loader.get("app.name") == "Test App"  # From default
        assert loader.get("app.debug") is True  # Overridden by dev
        assert loader.get("app.port") == 8001  # Overridden by dev
        
        # Should override database config
        assert loader.get("database.user") == "dev_user"  # Overridden by dev
        assert loader.get("database.password") == "dev_pass"  # Overridden by dev
        assert loader.get("database.type") == "mysql"  # From default
        
        # Should keep default cache config
        assert loader.get("cache.redis.host") == "localhost"
    
    def test_get_with_default_value(self):
        """Test getting configuration values with default fallback."""
        loader = EnvConfigLoader(env_name="dev", root_dir=self.temp_dir)
        
        # Existing value
        assert loader.get("app.name") == "Test App"
        
        # Non-existing value with default
        assert loader.get("nonexistent.key", "default_value") == "default_value"
        
        # Non-existing nested value
        assert loader.get("app.nonexistent", "fallback") == "fallback"
    
    def test_get_section(self):
        """Test getting entire configuration sections."""
        loader = EnvConfigLoader(env_name="dev", root_dir=self.temp_dir)
        
        # Get app section
        app_config = loader.get_section("app")
        assert app_config["name"] == "Test App"
        assert app_config["debug"] is True
        assert app_config["port"] == 8001
        
        # Get database section
        db_config = loader.get_section("database")
        assert db_config["user"] == "dev_user"
        assert db_config["type"] == "mysql"
        
        # Non-existing section
        assert loader.get_section("nonexistent") == {}
    
    def test_set_configuration_value(self):
        """Test setting configuration values."""
        loader = EnvConfigLoader(env_name="dev", root_dir=self.temp_dir)
        
        # Set new value
        loader.set("app.new_setting", "new_value")
        assert loader.get("app.new_setting") == "new_value"
        
        # Override existing value
        loader.set("app.port", 9000)
        assert loader.get("app.port") == 9000
        
        # Set nested value
        loader.set("new.nested.value", "test")
        assert loader.get("new.nested.value") == "test"
    
    def test_update_from_environment_variables(self):
        """Test updating configuration from environment variables."""
        loader = EnvConfigLoader(env_name="dev", root_dir=self.temp_dir)
        
        with patch.dict(os.environ, {
            "APP__PORT": "9999",
            "DATABASE__HOST": "remote-host",
            "CACHE__REDIS__TIMEOUT": "5",
            "NEW__CONFIG__VALUE": "env-value"
        }):
            loader.update_from_env()
            
            # Should override existing values
            assert loader.get("app.port") == 9999
            assert loader.get("database.host") == "remote-host"
            assert loader.get("cache.redis.timeout") == 5
            
            # Should create new nested structure
            assert loader.get("new.config.value") == "env-value"
    
    def test_environment_variable_type_conversion(self):
        """Test type conversion for environment variables."""
        loader = EnvConfigLoader(env_name="dev", root_dir=self.temp_dir)
        
        with patch.dict(os.environ, {
            "TEST__STRING": "hello",
            "TEST__INTEGER": "42",
            "TEST__FLOAT": "3.14",
            "TEST__BOOLEAN_TRUE": "true",
            "TEST__BOOLEAN_FALSE": "false",
            "TEST__BOOLEAN_YES": "yes",
            "TEST__BOOLEAN_NO": "no",
            "TEST__BOOLEAN_1": "1",
            "TEST__BOOLEAN_0": "0",
            "TEST__EMPTY": ""
        }):
            loader.update_from_env()
            
            assert loader.get("test.string") == "hello"
            assert loader.get("test.integer") == 42
            assert loader.get("test.float") == 3.14
            assert loader.get("test.boolean_true") is True
            assert loader.get("test.boolean_false") is False
            assert loader.get("test.boolean_yes") is True
            assert loader.get("test.boolean_no") is False
            assert loader.get("test.boolean_1") is True
            assert loader.get("test.boolean_0") is False
            assert loader.get("test.empty") == ""
    
    def test_env_name_from_environment(self):
        """Test environment name detection from APP_ENV environment variable."""
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            loader = EnvConfigLoader(root_dir=self.temp_dir)
            assert loader.env_name == "production"
        
        # Test default
        with patch.dict(os.environ, {}, clear=True):
            loader = EnvConfigLoader(root_dir=self.temp_dir)
            assert loader.env_name == "dev"
    
    def test_missing_default_config_file(self):
        """Test behavior when default config file is missing."""
        empty_dir = tempfile.mkdtemp()
        
        try:
            # Should not raise exception, just print warning
            loader = EnvConfigLoader(env_name="dev", root_dir=empty_dir)
            assert loader.config == {}
        finally:
            import shutil
            shutil.rmtree(empty_dir)
    
    def test_invalid_toml_file(self):
        """Test behavior with invalid TOML file."""
        # Create invalid TOML file
        with open(self.temp_path / "env.invalid.toml", "w") as f:
            f.write("invalid toml content [[[")
        
        # Should not crash, just print error
        loader = EnvConfigLoader(env_name="invalid", root_dir=self.temp_dir)
        # Should still have default config
        assert loader.get("app.name") == "Test App"
    
    def test_get_all_configuration(self):
        """Test getting complete configuration dictionary."""
        loader = EnvConfigLoader(env_name="dev", root_dir=self.temp_dir)
        
        all_config = loader.get_all()
        
        # Should be a copy, not reference
        assert all_config is not loader.config
        
        # Should contain merged configuration
        assert all_config["app"]["debug"] is True  # From dev
        assert all_config["app"]["name"] == "Test App"  # From default
        assert all_config["database"]["user"] == "dev_user"  # From dev
        assert all_config["cache"]["redis"]["host"] == "localhost"  # From default
    
    def test_repr(self):
        """Test string representation of EnvConfigLoader."""
        loader = EnvConfigLoader(env_name="test", root_dir="/tmp")
        expected = "EnvConfigLoader(env_name='test', root_dir='/tmp')"
        assert repr(loader) == expected


class TestEnvConfigLoaderIntegration:
    """Integration tests for EnvConfigLoader with actual config files."""
    
    @pytest.mark.integration
    def test_load_real_environment_config(self):
        """Test loading real environment configuration files."""
        # This test assumes the project has actual environment files
        project_root = Path(__file__).parent.parent.parent
        
        # Test loading default environment
        loader = EnvConfigLoader(env_name="dev", root_dir=project_root)
        
        # Basic structure should be loaded
        assert "app" in loader.config
        assert "database" in loader.config
        
        # Should have basic app configuration
        app_config = loader.get_section("app")
        assert "name" in app_config
        assert "host" in app_config
        assert "port" in app_config 