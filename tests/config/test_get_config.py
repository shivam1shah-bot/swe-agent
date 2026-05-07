"""
Tests for the get_config function and config system integration.
"""

import os
import tempfile
import toml
from pathlib import Path
from unittest.mock import patch

import pytest

from src.providers.config_loader import get_config, EnvConfigLoader


class TestGetConfig:
    """Test cases for the get_config function."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Clear global config instance to ensure clean state
        import src.providers.config_loader
        src.providers.config_loader._config_instance = None
        
        # Create minimal test configs
        self.default_config = {
            "app": {
                "name": "SWE Agent",
                "host": "0.0.0.0",
                "port": 8002,
                "debug": False
            },
            "database": {
                "type": "mysql",
                "host": "localhost",
                "port": 3306,
                "user": "swe_agent",
                "name": "swe_agent"
            },
            "environment": {
                "name": "default",
                "debug": False
            }
        }
        
        self.dev_config = {
            "app": {
                "debug": True
            },
            "database": {
                "user": "dev_user"
            },
            "environment": {
                "name": "dev",
                "debug": True
            }
        }
        
        # Create environments directory
        environments_dir = self.temp_path / "environments"
        environments_dir.mkdir(exist_ok=True)
        
        # Write config files
        with open(environments_dir / "env.default.toml", "w") as f:
            toml.dump(self.default_config, f)
            
        with open(environments_dir / "env.dev.toml", "w") as f:
            toml.dump(self.dev_config, f)
    
    def teardown_method(self):
        """Cleanup test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
        
        # Clear global config instance after each test
        import src.providers.config_loader
        src.providers.config_loader._config_instance = None
    
    @patch('src.providers.config_loader.EnvConfigLoader')
    def test_get_config_initialization(self, mock_loader_class):
        """Test that get_config properly initializes EnvConfigLoader."""
        mock_loader = mock_loader_class.return_value
        mock_loader.get_all.return_value = {"test": "config"}
        
        config = get_config()
        
        # Should initialize loader
        mock_loader_class.assert_called_once()
        mock_loader.update_from_env.assert_called_once()
        mock_loader.get_all.assert_called_once()
    
    def test_get_config_legacy_compatibility(self):
        """Test that get_config provides legacy compatibility fields."""
        # Mock the current working directory to use our temp dir
        with patch('pathlib.Path.cwd', return_value=self.temp_path):
            config = get_config()
            
            # Should have legacy compatibility fields
            assert "ENVIRONMENT" in config
            assert "DEBUG" in config
            assert "LOG_LEVEL" in config
            assert "ROOT_DIR" in config
            assert "UPLOAD_FOLDER" in config
            assert "ALLOWED_EXTENSIONS" in config
            assert "MAX_CONTENT_LENGTH" in config
            
            # Database legacy fields
            assert "MYSQL_DB_HOST" in config
            assert "MYSQL_DB_USER" in config
            assert "MYSQL_DB_PASS" in config
            assert "MYSQL_DB_NAME" in config
            
            # Schema and agent fields
            assert "DB_SCHEMA_VERSION" in config
            assert "DEFAULT_AGENT" in config
    
    def test_get_config_database_uri_generation(self):
        """Test that get_config generates database URI from components."""
        with patch('pathlib.Path.cwd', return_value=self.temp_path):
            with patch.dict(os.environ, {"APP_ENV": "default"}):
                config = get_config()
                
                # Should generate database URI
                assert "uri" in config["database"]
                expected_uri = "mysql+pymysql://swe_agent:password@localhost:3306/swe_agent"
                assert config["database"]["uri"] == expected_uri

    def test_get_config_root_dir_calculation(self):
        """Test that get_config calculates root directory correctly."""
        config = get_config()
        
        # Should set root_dir if not present
        assert "root_dir" in config
        assert config["root_dir"] is not None
        
        # Should set upload_folder based on root_dir
        assert "upload_folder" in config
        assert config["upload_folder"] == os.path.join(config["root_dir"], "uploads")
    
    def test_get_config_allowed_extensions(self):
        """Test that get_config sets allowed file extensions."""
        config = get_config()
        
        expected_extensions = {
            "txt", "pdf", "md", "c", "cpp", "py", "js", "html", "css", 
            "java", "rs", "go", "ts", "json", "yaml", "yml", "toml", 
            "sh", "ipynb", "jsx", "tsx"
        }
        
        assert config["allowed_extensions"] == expected_extensions
    
    def test_get_config_legacy_boolean_conversion(self):
        """Test legacy boolean field conversion."""
        with patch('pathlib.Path.cwd', return_value=self.temp_path):
            with patch.dict(os.environ, {"APP_ENV": "dev"}):
                config = get_config()
                
                # Boolean fields should be converted to 1/0
                assert config["DEBUG"] == 1  # debug=true in dev config
                assert config["SHOW_RECENT_TASKS"] == 0  # default false
    
    def test_get_config_environment_variable_override(self):
        """Test that environment variables override config values."""
        with patch('pathlib.Path.cwd', return_value=self.temp_path):
            with patch.dict(os.environ, {
                "APP_ENV": "dev",
                "APP__PORT": "9999",
                "DATABASE__HOST": "override-host"
            }):
                config = get_config()
                
                # Environment variables should override config
                assert config["app"]["port"] == 9999
                assert config["database"]["host"] == "override-host"
                
                # Other values should remain from config files
                assert config["app"]["debug"] is True  # From dev config
                assert config["app"]["name"] == "SWE Agent"  # From default config


class TestConfigSystemIntegration:
    """Integration tests for the complete config system."""
    
    @pytest.mark.integration
    def test_config_loading_with_real_files(self):
        """Test config loading with actual project files."""
        # This test runs against actual config files
        config = get_config()
        
        # Should have basic structure
        assert isinstance(config, dict)
        assert "app" in config or "ENVIRONMENT" in config
        
        # Should have legacy compatibility
        assert "ROOT_DIR" in config
        assert "ALLOWED_EXTENSIONS" in config
    
    @pytest.mark.unit
    def test_config_caching_behavior(self):
        """Test that config loading doesn't happen on every call."""
        # This would be important for performance
        # For now, we just ensure get_config returns consistent results
        config1 = get_config()
        config2 = get_config()
        
        # Should return equivalent configurations
        # Note: They might not be the same object due to copying
        assert config1.keys() == config2.keys()
    
    @pytest.mark.slow
    def test_config_performance(self):
        """Test config loading performance."""
        import time
        
        start_time = time.time()
        for _ in range(10):
            config = get_config()
        end_time = time.time()
        
        # Should complete quickly
        total_time = end_time - start_time
        assert total_time < 1.0, f"Config loading took {total_time:.2f}s for 10 calls"
    
    def test_config_with_missing_sections(self):
        """Test graceful handling of missing config sections."""
        config = get_config()
        
        # Should handle missing sections gracefully
        missing_value = config.get("nonexistent", {}).get("missing", "default")
        assert missing_value == "default"
    
    def test_config_validation_structure(self):
        """Test that config has expected basic structure."""
        config = get_config()
        
        # Core sections that should exist (either in new or legacy format)
        if "app" in config:
            # New TOML format
            assert isinstance(config["app"], dict)
        else:
            # Legacy format should have these keys
            expected_legacy_keys = [
                "ROOT_DIR", "ALLOWED_EXTENSIONS", "MAX_CONTENT_LENGTH"
            ]
            for key in expected_legacy_keys:
                assert key in config, f"Missing legacy config key: {key}"


class TestConfigErrorHandling:
    """Test error handling in the config system."""
    
    def test_config_with_corrupted_toml(self):
        """Test handling of corrupted TOML files."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        
        try:
            # Create corrupted TOML file
            with open(temp_path / "env.default.toml", "w") as f:
                f.write("invalid toml content ][[[")
            
            with patch('pathlib.Path.cwd', return_value=temp_path):
                # Should not crash
                config = get_config()
                # Should have fallback values
                assert isinstance(config, dict)
        finally:
            import shutil
            shutil.rmtree(temp_dir)
    
    def test_config_with_no_files(self):
        """Test config loading when no files exist."""
        temp_dir = tempfile.mkdtemp()
        
        try:
            with patch('pathlib.Path.cwd', return_value=temp_dir):
                # Should not crash
                config = get_config()
                # Should have basic structure from legacy compatibility
                assert isinstance(config, dict)
                assert "ALLOWED_EXTENSIONS" in config
        finally:
            import shutil
            shutil.rmtree(temp_dir) 