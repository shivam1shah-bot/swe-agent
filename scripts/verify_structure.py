#!/usr/bin/env python3
"""
Structure Verification Script

Long-term structural validation for the SWE Agent repository.
Checks essential configuration and routing that must remain valid.

Usage:
    python scripts/verify_structure.py

Exit codes:
    0 - All checks passed
    1 - Errors found
"""

import sys
from pathlib import Path


def check_toml_configs():
    """Validate TOML configuration files are parseable and have required sections."""
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        import tomli as tomllib  # Fallback

    errors = []

    for env_file in Path("environments").glob("*.toml"):
        try:
            with open(env_file, "rb") as f:
                config = tomllib.load(f)

            # Check for [discover] section
            if "discover" not in config:
                errors.append(f"{env_file}: Missing [discover] section")
            else:
                discover = config["discover"]
                if "backend_url" not in discover:
                    errors.append(f"{env_file}: discover.backend_url not set")

            # Check for [auth.users] section with discover_service (Basic Auth)
            auth = config.get("auth", {})
            if "users" not in auth:
                errors.append(f"{env_file}: Missing [auth.users] section")
            else:
                auth_users = auth["users"]
                if "discover_service" not in auth_users:
                    errors.append(f"{env_file}: Missing discover_service in [auth.users]")

        except Exception as e:
            errors.append(f"{env_file}: Parse error - {e}")

    if errors:
        print("❌ Configuration errors:")
        for err in errors:
            print(f"  - {err}")
        return False

    print("✅ TOML configurations valid")
    return True


def check_router_registration():
    """Verify Discover router is properly registered."""
    errors = []

    # Check __init__.py exports discover
    init_file = Path("src/api/routers/__init__.py")
    if init_file.exists():
        content = init_file.read_text()
        if "discover" not in content:
            errors.append("routers/__init__.py does not export 'discover'")
    else:
        errors.append("routers/__init__.py not found")

    # Check api.py registers discover router
    api_file = Path("src/api/api.py")
    if api_file.exists():
        content = api_file.read_text()
        if "discover.router" not in content:
            errors.append("api.py does not register discover.router")
        if 'tags=["discover"]' not in content:
            errors.append("api.py discover router missing correct tags")
    else:
        errors.append("api.py not found")

    if errors:
        print("❌ Router registration errors:")
        for err in errors:
            print(f"  - {err}")
        return False

    print("✅ Router registration valid")
    return True


def check_ui_env_files():
    """Verify UI environment files have required variables."""
    env_files = [
        "ui/environments/env.default",
        "ui/environments/env.dev",
        "ui/environments/env.stage",
        "ui/environments/env.prod",
    ]

    errors = []
    for env_file in env_files:
        path = Path(env_file)
        if not path.exists():
            errors.append(f"{env_file}: File not found")
            continue

        content = path.read_text()
        if "APP_UI_PORT=" not in content and "Inherits from env.default" not in content:
            errors.append(f"{env_file}: Missing APP_UI_PORT")

    if errors:
        print("❌ UI environment errors:")
        for err in errors:
            print(f"  - {err}")
        return False

    print("✅ UI environment files valid")
    return True


def main():
    """Run all structure verification checks."""
    print("🔍 Structure Verification")
    print("=" * 40)

    checks = [
        ("TOML Configs", check_toml_configs),
        ("Router Registration", check_router_registration),
        ("UI Env Files", check_ui_env_files),
    ]

    passed = 0
    failed = 0

    for name, check_fn in checks:
        print(f"\n🧪 {name}...", end=" ")
        try:
            if check_fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ ERROR: {e}")
            failed += 1

    print("\n" + "=" * 40)
    print(f"Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("✅ Structure verification passed")
        return 0
    else:
        print("❌ Structure verification failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
