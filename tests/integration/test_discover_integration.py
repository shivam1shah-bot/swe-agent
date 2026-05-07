"""
Integration tests for Discover UI integration.

These tests verify the subtle risks that might pass CI but fail in deployment:
1. Port configuration changes
2. Token exchange configuration
3. Router registration
4. Environment variable consistency
"""

import os
import pytest
from pathlib import Path


class TestPortConfiguration:
    """Tests for port configuration changes (26379→26389, 28004→28014)."""

    def test_docker_compose_uses_new_redis_port(self):
        """Verify Redis port updated from 26379 to 26389."""
        docker_compose = Path("docker-compose.dev.yml")
        if not docker_compose.exists():
            pytest.skip("docker-compose.dev.yml not found")
        
        content = docker_compose.read_text()
        
        # Should use new port
        assert "26389:6379" in content, "Redis port should be 26389:6379"
        # Should NOT use old port
        assert "26379:6379" not in content, "Old Redis port 26379 should not be present"

    def test_docker_compose_uses_new_webhook_port(self):
        """Verify Webhook receiver port updated from 28004 to 28014."""
        docker_compose = Path("docker-compose.dev.yml")
        if not docker_compose.exists():
            pytest.skip("docker-compose.dev.yml not found")
        
        content = docker_compose.read_text()
        
        # Should use new port
        assert "28014:8004" in content, "Webhook port should be 28014:8004"
        # Should NOT use old port
        assert "28004:8004" not in content, "Old webhook port 28004 should not be present"


class TestUIEnvironmentConfiguration:
    """Tests for UI environment variable changes."""

    def test_app_ui_port_in_default_env(self):
        """Verify APP_UI_PORT exists in default env file."""
        env_file = Path("ui/environments/env.default")
        if not env_file.exists():
            pytest.skip("env.default not found")
        
        content = env_file.read_text()
        assert "APP_UI_PORT=" in content, "APP_UI_PORT should be defined"
        # Extract and validate it's a number
        for line in content.split("\n"):
            if line.startswith("APP_UI_PORT="):
                port = line.split("=")[1].strip().strip('"')
                assert port.isdigit(), f"APP_UI_PORT should be a number, got: {port}"
                assert 1024 <= int(port) <= 65535, f"APP_UI_PORT should be valid port range"

    @pytest.mark.parametrize("env", ["dev", "stage", "prod", "dev_docker"])
    def test_app_ui_port_in_env_files(self, env):
        """Verify APP_UI_PORT exists in all environment files."""
        env_file = Path(f"ui/environments/env.{env}")
        if not env_file.exists():
            pytest.skip(f"env.{env} not found")
        
        content = env_file.read_text()
        # All env files must explicitly define APP_UI_PORT
        assert "APP_UI_PORT=" in content, f"env.{env} should have APP_UI_PORT explicitly defined"


class TestDiscoverConfiguration:
    """Tests for Discover backend configuration with service-to-service auth."""

    @pytest.mark.parametrize("env_file", [
        "environments/env.default.toml",
        "environments/env.stage.toml",
        "environments/env.prod.toml"
    ])
    def test_discover_config_section_exists(self, env_file):
        """Verify [discover] section exists in TOML configs."""
        path = Path(env_file)
        if not path.exists():
            pytest.skip(f"{env_file} not found")
        
        content = path.read_text()
        assert "[discover]" in content, f"{env_file} should have [discover] section"
        assert "backend_url" in content, f"{env_file} should have backend_url"

    @pytest.mark.parametrize("env_file", [
        "environments/env.default.toml",
        "environments/env.stage.toml",
        "environments/env.prod.toml"
    ])
    def test_discover_service_account_exists(self, env_file):
        """Verify discover_service account exists in auth.users for service-to-service auth."""
        path = Path(env_file)
        if not path.exists():
            pytest.skip(f"{env_file} not found")

        content = path.read_text()
        assert "[auth.users]" in content, f"{env_file} should have [auth.users] section"
        assert "discover_service" in content, f"{env_file} should have discover_service account"

    @pytest.mark.parametrize("env_file", [
        "environments/env.default.toml",
        "environments/env.stage.toml",
        "environments/env.prod.toml"
    ])
    def test_no_token_exchange_config(self, env_file):
        """Verify old token_exchange section has been removed."""
        path = Path(env_file)
        if not path.exists():
            pytest.skip(f"{env_file} not found")

        content = path.read_text()
        # Token exchange has been replaced with Basic Auth
        assert "[token_exchange]" not in content, f"{env_file} should not have [token_exchange] section (replaced with Basic Auth)"


class TestFlaskRemoval:
    """Tests to verify Flask has been completely removed."""

    def test_no_flask_in_requirements(self):
        """Verify Flask dependencies removed from requirements.txt."""
        req_file = Path("requirements.txt")
        if not req_file.exists():
            pytest.skip("requirements.txt not found")
        
        content = req_file.read_text().lower()
        flask_packages = ["flask", "werkzeug", "jinja2", "itsdangerous", "flask-cors"]
        
        for pkg in flask_packages:
            assert pkg not in content, f"{pkg} should not be in requirements.txt"

    def test_no_flask_imports_in_src(self):
        """Verify no Flask imports remain in source code."""
        src_dir = Path("src")
        if not src_dir.exists():
            pytest.skip("src directory not found")
        
        flask_patterns = ["from flask", "import flask", "Flask("]
        
        for py_file in src_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            
            content = py_file.read_text()
            for pattern in flask_patterns:
                assert pattern not in content, f"Found '{pattern}' in {py_file}"

    def test_no_flask_in_commands(self):
        """Verify no Flask usage in commands directory."""
        commands_dir = Path("commands")
        if not commands_dir.exists():
            pytest.skip("commands directory not found")
        
        flask_patterns = ["from flask", "import flask", "Flask("]
        
        for py_file in commands_dir.glob("*.py"):
            content = py_file.read_text()
            for pattern in flask_patterns:
                assert pattern not in content, f"Found '{pattern}' in {py_file}"


class TestYarnMigration:
    """Tests for Yarn 4 migration."""

    def test_yarnrc_exists(self):
        """Verify .yarnrc.yml exists for Yarn 4."""
        yarnrc = Path("ui/.yarnrc.yml")
        assert yarnrc.exists(), ".yarnrc.yml should exist for Yarn 4"

    def test_yarn_releases_directory_exists(self):
        """Verify Yarn 4 binary is committed."""
        yarn_releases = Path("ui/.yarn/releases")
        assert yarn_releases.exists(), ".yarn/releases should exist"
        assert any(yarn_releases.iterdir()), ".yarn/releases should contain Yarn binary"

    def test_package_manager_set_in_package_json(self):
        """Verify packageManager field in package.json."""
        package_json = Path("ui/package.json")
        if not package_json.exists():
            pytest.skip("package.json not found")
        
        import json
        with open(package_json) as f:
            pkg = json.load(f)
        
        assert "packageManager" in pkg, "package.json should have packageManager field"
        assert pkg["packageManager"].startswith("yarn@"), "packageManager should be yarn"

    def test_package_lock_removed(self):
        """Verify package-lock.json removed for Yarn."""
        package_lock = Path("ui/package-lock.json")
        assert not package_lock.exists(), "package-lock.json should be removed when using Yarn"


class TestDiscoverRouter:
    """Tests for Discover API router registration."""

    def test_discover_router_exported(self):
        """Verify discover router is exported from routers package."""
        init_file = Path("src/api/routers/__init__.py")
        if not init_file.exists():
            pytest.skip("routers/__init__.py not found")
        
        content = init_file.read_text()
        assert "discover" in content, "discover should be exported from routers"
        assert '"discover"' in content or "'discover'" in content or "discover," in content, \
            "discover should be in __all__"

    def test_discover_router_registered_in_api(self):
        """Verify discover router is registered in api.py."""
        api_file = Path("src/api/api.py")
        if not api_file.exists():
            pytest.skip("api.py not found")
        
        content = api_file.read_text()
        assert "discover.router" in content, "discover.router should be registered"
        assert 'tags=["discover"]' in content, "discover router should have correct tags"


class TestBuildConfiguration:
    """Tests for build configuration (Tailwind v4, etc.)."""

    def test_postcss_uses_tailwindcss_v4(self):
        """Verify PostCSS config uses @tailwindcss/postcss."""
        postcss_config = Path("ui/postcss.config.js")
        if not postcss_config.exists():
            pytest.skip("postcss.config.js not found")
        
        content = postcss_config.read_text()
        assert "'@tailwindcss/postcss'" in content or '"@tailwindcss/postcss"' in content, \
            "PostCSS should use @tailwindcss/postcss for v4"
        # Should NOT use old tailwindcss plugin
        assert "'tailwindcss'" not in content or content.count("tailwindcss") == 0, \
            "PostCSS should not use old tailwindcss plugin"

    def test_index_css_uses_v4_syntax(self):
        """Verify index.css uses Tailwind v4 @import syntax."""
        index_css = Path("ui/src/index.css")
        if not index_css.exists():
            pytest.skip("index.css not found")
        
        content = index_css.read_text()
        # Should use v4 import syntax
        assert '@import "tailwindcss"' in content, \
            "index.css should use @import 'tailwindcss' for v4"
        # Should NOT use v3 directives
        assert "@tailwind base" not in content, "Should not use @tailwind base (v3 syntax)"
        assert "@tailwind components" not in content, "Should not use @tailwind components (v3 syntax)"
        assert "@tailwind utilities" not in content, "Should not use @tailwind utilities (v3 syntax)"


class TestMakefileUpdates:
    """Tests for Makefile updates."""

    def test_makefile_uses_yarn(self):
        """Verify Makefile uses yarn commands."""
        makefile = Path("Makefile")
        if not makefile.exists():
            pytest.skip("Makefile not found")
        
        content = makefile.read_text()
        assert "yarn install" in content, "Makefile should use yarn install"
        assert "yarn dev" in content, "Makefile should use yarn dev"

    def test_makefile_checks_corepack(self):
        """Verify Makefile checks for corepack availability."""
        makefile = Path("Makefile")
        if not makefile.exists():
            pytest.skip("Makefile not found")
        
        content = makefile.read_text()
        assert "corepack enable" in content or "command -v yarn" in content, \
            "Makefile should verify Yarn/Corepack is available"


class TestDiscoverServices:
    """Tests for Discover UI services."""

    def test_discover_services_use_correct_api_url(self):
        """Verify Discover services use getApiBaseUrl (proxied through Python API)."""
        services_dir = Path("ui/src/services/discover")
        if not services_dir.exists():
            pytest.skip("Discover services directory not found")
        
        for service_file in services_dir.glob("*.service.ts"):
            content = service_file.read_text()
            # Discover services now use main API via Python proxy at /api/v1/discover/*
            assert "getApiBaseUrl" in content, \
                f"{service_file.name} should use getApiBaseUrl"
            # Should call Discover endpoints through Python proxy
            assert "/api/v1/discover/" in content, \
                f"{service_file.name} should use /api/v1/discover/ paths"

    def test_discover_services_have_error_classes(self):
        """Verify Discover services export error classes."""
        services_dir = Path("ui/src/services/discover")
        if not services_dir.exists():
            pytest.skip("Discover services directory not found")
        
        expected_errors = [
            "ConversationServiceError",
            "CredentialsServiceError",
            "HandoffServiceError",
            "ToolsServiceError"
        ]
        
        for error_class in expected_errors:
            found = False
            for service_file in services_dir.glob("*.service.ts"):
                content = service_file.read_text()
                if f"class {error_class}" in content or f"export class {error_class}" in content:
                    found = True
                    break
            assert found, f"{error_class} should be defined in a service file"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
