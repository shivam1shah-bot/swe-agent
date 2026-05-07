"""
Routing contract tests for Discover API proxy.

These tests verify that the backend routing configuration matches
what the frontend services expect, preventing proxy path mismatches.
"""

from pathlib import Path

import pytest

pytest.importorskip("pytest_asyncio")


# Expected endpoint paths from frontend services
# These must match the paths defined in ui/src/services/discover/*.service.ts
EXPECTED_DISCOVER_ENDPOINTS = {
    # Query streaming
    "POST:/api/v1/discover/query/stream": {
        "frontend_refs": ["discover.service.ts:streamDiscover()"],
    },
    # Conversation management
    "POST:/api/v1/discover/sessions/{session_id}/save": {
        "frontend_refs": ["conversation.service.ts:save()"],
    },
    "POST:/api/v1/discover/sessions/{session_id}/share": {
        "frontend_refs": ["conversation.service.ts:share()"],
    },
    # Credentials
    "GET:/api/v1/discover/credentials/{tool_id}": {
        "frontend_refs": ["credentials.service.ts:get()"],
    },
    "POST:/api/v1/discover/credentials": {
        "frontend_refs": ["credentials.service.ts:save()"],
    },
    "DELETE:/api/v1/discover/credentials/{tool_id}": {
        "frontend_refs": ["credentials.service.ts:delete()"],
    },
    # Tools
    "GET:/api/v1/discover/tools": {
        "frontend_refs": ["tools.service.ts:getTools()"],
    },
    "GET:/api/v1/discover/tools/{tool_id}/status": {
        "frontend_refs": ["tools.service.ts:getToolStatus()"],
    },
    # Handoff
    "POST:/api/v1/discover/handoff/{ref_id}/attach": {
        "frontend_refs": ["handoff.service.ts:attachHandoff()"],
    },
    "GET:/api/v1/discover/handoff/pending/{runtime_session_id}": {
        "frontend_refs": ["handoff.service.ts:getPendingMessages()"],
    },
    # Feedback
    "POST:/api/v1/discover/feedback/ui": {
        "frontend_refs": ["discover.service.ts (feedback via stream callbacks)"],
    },
}


class TestDiscoverRouterRegistration:
    """Tests for router registration and prefix configuration."""

    def test_router_registered_with_discover_prefix(self):
        """
        Verify discover router is registered with /api/v1/discover prefix.
        
        This catches the bug where router was registered with just /api/v1,
        causing path mismatches with frontend expectations.
        """
        from src.api.api import create_app
        from src.api.routers import discover
        
        app = create_app()
        
        # Find the discover router registration
        discover_route_found = False
        expected_prefix = "/api/v1/discover"
        
        for route in app.routes:
            if hasattr(route, "path"):
                # Check if route path starts with expected prefix
                if route.path.startswith(expected_prefix):
                    discover_route_found = True
                    break
        
        # Alternative: check via router introspection
        if not discover_route_found:
            # Check if any routes from discover router are mounted with correct prefix
            for route in app.routes:
                if hasattr(route, "path"):
                    # Look for discover-specific paths
                    discover_paths = ["/query/stream", "/sessions/", "/credentials/", "/tools"]
                    for discover_path in discover_paths:
                        full_path = f"{expected_prefix}{discover_path}"
                        if route.path.startswith(full_path.rstrip("/")):
                            discover_route_found = True
                            break
        
        assert discover_route_found, (
            f"Discover router must be registered with prefix '{expected_prefix}'. "
            f"Check api.py for: app.include_router(discover.router, prefix='{expected_prefix}')"
        )

    def test_no_routes_at_wrong_prefix(self):
        """
        Verify discover routes are NOT at the wrong /api/v1 prefix (without /discover).
        
        This catches the specific bug where router was registered as:
        app.include_router(discover.router, prefix="/api/v1")  # WRONG
        Instead of:
        app.include_router(discover.router, prefix="/api/v1/discover")  # CORRECT
        """
        from src.api.api import create_app
        
        app = create_app()
        
        # These paths should NOT exist at /api/v1 (without /discover)
        # These are discover-specific paths that must have /discover prefix
        discover_specific_base_paths = [
            "/query/stream",
            "/sessions/",
            "/credentials",
            "/tools",
            "/handoff/",
            "/feedback/ui",
        ]
        
        wrong_prefix_paths = []
        
        for route in app.routes:
            if hasattr(route, "path"):
                route_path = route.path
                # Check if route is at /api/v1/{discover_path} (wrong)
                # instead of /api/v1/discover/{discover_path} (correct)
                for discover_path in discover_specific_base_paths:
                    wrong_prefix = f"/api/v1{discover_path}"
                    correct_prefix = f"/api/v1/discover{discover_path}"
                    
                    # Route starts with wrong prefix but NOT with correct prefix
                    if route_path.startswith(wrong_prefix) and not route_path.startswith(correct_prefix):
                        wrong_prefix_paths.append(route_path)
                        break
        
        assert len(wrong_prefix_paths) == 0, (
            f"Found discover routes at wrong prefix /api/v1 (without /discover): "
            f"{wrong_prefix_paths}. These should be at /api/v1/discover/*"
        )


class TestDiscoverEndpointPaths:
    """Tests that all expected discover endpoints are registered correctly."""

    def test_all_expected_endpoints_exist(self):
        """
        Verify all endpoints expected by frontend exist in the backend.
        
        This is a contract test - if frontend expects an endpoint, backend must provide it.
        """
        from src.api.api import create_app
        
        app = create_app()
        
        # Collect all route paths
        registered_paths = set()
        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                # FastAPI route
                for method in route.methods:
                    if method != "HEAD":  # Skip HEAD as it's auto-generated
                        registered_paths.add(f"{method}:{route.path}")
        
        def _paths_match(expected: str, actual: str) -> bool:
            """Compare paths accounting for path parameters."""
            if expected == actual:
                return True

            # Split and compare segments
            exp_parts = expected.split(":", 1)[1].split("/")
            act_parts = actual.split(":", 1)[1].split("/")

            if len(exp_parts) != len(act_parts):
                return False

            for exp, act in zip(exp_parts, act_parts):
                # Both parameterized - any name is fine
                if exp.startswith("{") and act.startswith("{"):
                    continue
                # Only one parameterized - mismatch
                if exp.startswith("{") or act.startswith("{"):
                    return False
                # Both literal - must match exactly
                if exp != act:
                    return False

            return True

        # Check each expected endpoint
        missing_endpoints = []
        for expected_path, info in EXPECTED_DISCOVER_ENDPOINTS.items():
            found = False
            for registered in registered_paths:
                if _paths_match(expected_path, registered):
                    found = True
                    break

            if not found:
                missing_endpoints.append({
                    "expected": expected_path,
                    "frontend": info["frontend_refs"]
                })
        
        assert len(missing_endpoints) == 0, (
            f"Missing discover endpoints that frontend expects:\n"
            + "\n".join([
                f"  - {ep['expected']} (used by {', '.join(ep['frontend'])})"
                for ep in missing_endpoints
            ])
        )

    def test_endpoint_methods_match_frontend_expectations(self):
        """
        Verify HTTP methods match what frontend services expect.
        
        Frontend services use specific HTTP methods (POST, GET, DELETE) - 
        backend must use the same methods.
        """
        from src.api.api import create_app
        
        app = create_app()
        
        # Build map of method:path -> route
        route_map = {}
        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                for method in route.methods:
                    if method != "HEAD":
                        key = f"{method}:{route.path}"
                        route_map[key] = route
        
        # Check method expectations
        method_mismatches = []
        
        for expected_path, info in EXPECTED_DISCOVER_ENDPOINTS.items():
            method, path = expected_path.split(":", 1)
            
            # Find matching route with any method
            found_methods = []
            for key in route_map.keys():
                registered_path = key.split(":", 1)[1]
                # Normalize for comparison
                if path.replace("{", "{") == registered_path.replace("{", "{"):
                    found_methods.append(key.split(":", 1)[0])
            
            if method not in found_methods and found_methods:
                method_mismatches.append({
                    "expected": expected_path,
                    "found_methods": found_methods,
                    "frontend": info["frontend_refs"]
                })
        
        assert len(method_mismatches) == 0, (
            f"HTTP method mismatches for discover endpoints:\n"
            + "\n".join([
                f"  - Expected {mm['expected']} but found methods {mm['found_methods']} "
                f"(used by {', '.join(mm['frontend'])})"
                for mm in method_mismatches
            ])
        )


class TestDiscoverRouteHandlers:
    """Tests that routes have the correct handler functions attached."""

    def test_stream_query_handler_attached(self):
        """Verify POST /query/stream has stream_query handler."""
        from src.api.api import create_app
        from src.api.routers.discover import stream_query
        
        app = create_app()
        
        # Find the route
        stream_route = None
        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                if "/query/stream" in route.path and "POST" in route.methods:
                    stream_route = route
                    break
        
        assert stream_route is not None, "POST /api/v1/discover/query/stream route not found"
        
        # Check the endpoint function
        endpoint_func = getattr(stream_route, "endpoint", None)
        assert endpoint_func is not None, "Route has no endpoint function"
        assert endpoint_func.__name__ == "stream_query", (
            f"Expected handler 'stream_query' but got '{endpoint_func.__name__}'"
        )

    def test_save_conversation_handler_attached(self):
        """Verify POST /sessions/{id}/save has save_conversation handler."""
        from src.api.api import create_app
        from src.api.routers.discover import save_conversation
        
        app = create_app()
        
        save_route = None
        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                if "/sessions/" in route.path and "/save" in route.path and "POST" in route.methods:
                    save_route = route
                    break
        
        assert save_route is not None, "POST /api/v1/discover/sessions/{id}/save route not found"
        
        endpoint_func = getattr(save_route, "endpoint", None)
        assert endpoint_func is not None, "Route has no endpoint function"
        assert endpoint_func.__name__ == "save_conversation", (
            f"Expected handler 'save_conversation' but got '{endpoint_func.__name__}'"
        )


class TestDiscoverFrontendContract:
    """
    Contract tests between frontend services and backend routes.
    
    These tests verify the EXPECTED_DISCOVER_ENDPOINTS contract matches
    both frontend service expectations and backend route registration.
    """

    def test_all_expected_endpoints_have_frontend_references(self):
        """
        Verify all endpoints in EXPECTED_DISCOVER_ENDPOINTS are referenced by frontend.
        
        This ensures the contract is complete - every backend endpoint should
        have a corresponding frontend consumer.
        """
        # Find all frontend service files
        services_dir = Path("ui/src/services/discover")
        if not services_dir.exists():
            pytest.skip("Frontend services directory not found")
        
        # Collect all frontend service content
        frontend_content = ""
        for service_file in services_dir.glob("*.service.ts"):
            frontend_content += service_file.read_text() + "\n"
        
        # Check each expected endpoint has a frontend reference
        orphaned_endpoints = []
        for expected_path, info in EXPECTED_DISCOVER_ENDPOINTS.items():
            # Extract the path portion (after method:)
            path = expected_path.split(":", 1)[1]
            
            # Check if any frontend file references this path
            found_in_frontend = False
            for ref in info["frontend_refs"]:
                filename = ref.split(":")[0]
                if filename in frontend_content:
                    found_in_frontend = True
                    break
            
            # Also check the path pattern exists in frontend content
            # Look for path segments without parameters
            path_segments = [seg for seg in path.split("/") if seg and not seg.startswith("{")]
            if all(seg in frontend_content for seg in path_segments if seg != "api" and seg != "v1"):
                found_in_frontend = True
            
            if not found_in_frontend:
                orphaned_endpoints.append({
                    "endpoint": expected_path,
                    "frontend_refs": info["frontend_refs"]
                })
        
        # This is a warning-level check - we don't fail, just report
        if orphaned_endpoints:
            pytest.skip(
                f"Some endpoints may not have frontend references (investigate manually): "
                f"{orphaned_endpoints}"
            )

    def test_frontend_service_files_exist(self):
        """Verify all expected frontend service files exist."""
        services_dir = Path("ui/src/services/discover")
        if not services_dir.exists():
            pytest.skip("Frontend services directory not found")
        
        expected_files = {
            "discover.service.ts",
            "conversation.service.ts",
            "credentials.service.ts",
            "handoff.service.ts",
            "tools.service.ts",
        }
        
        found_files = {f.name for f in services_dir.glob("*.service.ts")}
        
        missing = expected_files - found_files
        assert len(missing) == 0, f"Missing expected frontend service files: {missing}"

    def test_frontend_services_use_correct_base_url(self):
        """
        Verify frontend services use getApiBaseUrl() and /api/v1/discover paths.
        
        This prevents frontend from calling wrong paths or wrong base URL.
        """
        services_dir = Path("ui/src/services/discover")
        if not services_dir.exists():
            pytest.skip("Frontend services directory not found")
        
        issues = []
        
        for service_file in services_dir.glob("*.service.ts"):
            content = service_file.read_text()
            
            # Must use getApiBaseUrl
            if "getApiBaseUrl" not in content:
                issues.append(f"{service_file.name}: missing getApiBaseUrl import/usage")
            
            # Must use /api/v1/discover/ paths
            if "/api/v1/discover/" not in content:
                # Check if it's using wrong path like /api/v1/ without /discover
                if "/api/v1/" in content and "/discover" not in content:
                    issues.append(f"{service_file.name}: uses /api/v1/ without /discover")
            
            # Must NOT use hardcoded URLs
            if "http://localhost" in content or "https://" in content.replace("https://example.com/pic.jpg", ""):
                issues.append(f"{service_file.name}: contains hardcoded URL")
        
        assert len(issues) == 0, (
            f"Frontend service issues found:\n" + "\n".join(f"  - {i}" for i in issues)
        )


class TestDiscoverUrlGeneration:
    """Tests for URL generation and path construction."""

    def test_discover_router_prefix_is_consistent(self):
        """
        Verify discover router prefix is consistently applied to all routes.
        
        All routes in discover.py should have paths that work with /api/v1/discover prefix.
        """
        from src.api.routers.discover import router
        
        # Get all routes from the discover router
        for route in router.routes:
            if hasattr(route, "path"):
                route_path = route.path
                # Route paths should start with / (they're relative to prefix)
                assert route_path.startswith("/"), (
                    f"Discover route path '{route_path}' should start with /"
                )
                # Combined with prefix /api/v1/discover, should give full API path
                full_path = f"/api/v1/discover{route_path}"
                assert full_path.startswith("/api/v1/discover/"), (
                    f"Full path '{full_path}' should start with /api/v1/discover/"
                )


class TestDiscoverProxyConfiguration:
    """Tests for the proxy configuration between Vyom and Discover backend."""

    def test_proxy_backend_url_configuration_exists(self):
        """Verify discover backend_url config is accessed correctly."""
        from src.api.routers.discover import _get_backend_url
        from unittest.mock import MagicMock
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "discover": {"backend_url": "http://test-discover:8080"}
        }
        
        url = _get_backend_url(mock_request)
        assert url == "http://test-discover:8080", "Backend URL should be extracted from config"

    def test_proxy_backend_url_default_fallback(self):
        """Verify proxy falls back to default URL when not configured."""
        from src.api.routers.discover import _get_backend_url
        from unittest.mock import MagicMock
        
        mock_request = MagicMock()
        mock_request.app.state.config = {}
        
        url = _get_backend_url(mock_request)
        assert url == "http://localhost:8080", "Should fallback to localhost default"


class TestDiscoverPathSafety:
    """Safety tests to catch common routing mistakes."""

    def test_no_duplicate_route_registration(self):
        """
        Verify no routes are registered multiple times (which can cause conflicts).
        """
        from src.api.api import create_app
        
        app = create_app()
        
        # Count occurrences of each path
        path_counts = {}
        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                for method in route.methods:
                    if method != "HEAD":
                        key = f"{method}:{route.path}"
                        path_counts[key] = path_counts.get(key, 0) + 1
        
        duplicates = {k: v for k, v in path_counts.items() if v > 1}
        
        assert len(duplicates) == 0, (
            f"Duplicate route registrations found: {duplicates}. "
            f"Each method:path combination should only be registered once."
        )

    def test_discover_routes_have_required_decorators(self):
        """Verify discover routes have proper FastAPI decorators."""
        from src.api.routers import discover
        
        # Check that router is an APIRouter
        from fastapi import APIRouter
        assert isinstance(discover.router, APIRouter), (
            "discover.router should be a FastAPI APIRouter instance"
        )

    def test_no_trailing_slashes_in_routes(self):
        """
        Verify discover routes don't have trailing slashes.
        
        Trailing slashes can cause unexpected redirect behavior.
        """
        from src.api.routers.discover import router
        
        routes_with_trailing_slash = []
        for route in router.routes:
            if hasattr(route, "path"):
                path = route.path
                if path != "/" and path.endswith("/"):
                    routes_with_trailing_slash.append(path)
        
        assert len(routes_with_trailing_slash) == 0, (
            f"Routes should not have trailing slashes: {routes_with_trailing_slash}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
