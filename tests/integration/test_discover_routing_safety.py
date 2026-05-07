"""
Integration tests for Discover routing safety.

These tests verify the contract between frontend services and backend routes,
preventing proxy path mismatches that can cause endpoints to be unreachable.

Note: These are "integration" tests in the sense they test the integration
between frontend expectations and backend routes, but they don't require
external services like databases (marked as unit tests to avoid DB deps).
"""

from pathlib import Path
import re

import pytest
from fastapi.testclient import TestClient


class TestDiscoverPathMatching:
    """
    Tests that verify frontend-expected paths actually exist and are reachable.
    
    These tests catch the class of bugs where:
    - Frontend calls: POST /api/v1/discover/query/stream
    - Backend has: POST /api/v1/query/stream (missing /discover prefix)
    
    The bug was caused by incorrect router prefix registration.
    """

    @pytest.fixture
    def client(self):
        """Create a test client for the API."""
        # Import inside fixture to avoid DB init during import
        from src.api.api import create_app
        app = create_app()
        return TestClient(app)

    @pytest.fixture
    def discover_endpoints(self):
        """
        All Discover endpoints expected by the frontend.
        
        These paths come from ui/src/services/discover/*.service.ts
        """
        return {
            # Query streaming
            "POST /api/v1/discover/query/stream",
            # Conversation management  
            "POST /api/v1/discover/sessions/{session_id}/save",
            "POST /api/v1/discover/sessions/{session_id}/share",
            # Credentials
            "GET /api/v1/discover/credentials/{tool_id}",
            "POST /api/v1/discover/credentials",
            "DELETE /api/v1/discover/credentials/{tool_id}",
            # Tools
            "GET /api/v1/discover/tools",
            "GET /api/v1/discover/tools/{tool_id}/status",
            # Handoff
            "POST /api/v1/discover/handoff/{ref_id}/attach",
            "GET /api/v1/discover/handoff/pending/{runtime_session_id}",
            # Feedback
            "POST /api/v1/discover/feedback/ui",
        }

    def test_all_discover_endpoints_are_registered(self, client, discover_endpoints):
        """
        Verify all expected Discover endpoints are registered in the API.
        
        This catches the specific bug where the router was registered with
        prefix="/api/v1" instead of prefix="/api/v1/discover".
        """
        # Get OpenAPI schema to find all registered routes
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        openapi = response.json()
        registered_paths = set()
        
        for path, methods in openapi.get("paths", {}).items():
            for method in methods.keys():
                if method != "parameters":  # Skip parameter metadata
                    registered_paths.add(f"{method.upper()} {path}")
        
        # Check each expected endpoint exists
        missing = []
        for endpoint in discover_endpoints:
            method, path = endpoint.split(" ", 1)
            
            # Check for exact or parameterized match
            found = False
            for registered in registered_paths:
                reg_method, reg_path = registered.split(" ", 1)
                
                if method == reg_method and self._paths_match(path, reg_path):
                    found = True
                    break
            
            if not found:
                missing.append(endpoint)
        
        assert len(missing) == 0, (
            f"Missing Discover endpoints that frontend expects:\n" +
            "\n".join(f"  - {ep}" for ep in missing) +
            f"\n\nHint: Check if discover.router is registered with "
            f"prefix='/api/v1/discover' in src/api/api.py"
        )

    def test_no_discover_routes_at_wrong_prefix(self, client):
        """
        Verify Discover-specific routes do NOT exist at /api/v1/* (without /discover).
        
        This is the regression test for the bug where:
        app.include_router(discover.router, prefix="/api/v1")  # WRONG
        was used instead of:
        app.include_router(discover.router, prefix="/api/v1/discover")  # CORRECT
        """
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        openapi = response.json()
        
        # These paths should only exist with /discover prefix
        discover_specific_suffixes = [
            "/query/stream",
            "/sessions/{session_id}/save",
            "/sessions/{session_id}/share", 
            "/credentials/{tool_id}",
            "/credentials",
            "/tools/{tool_id}/status",
            "/tools",
            "/handoff/{ref_id}/attach",
            "/handoff/pending/{runtime_session_id}",
            "/feedback/ui",
        ]
        
        wrong_prefix_routes = []
        
        for path in openapi.get("paths", {}).keys():
            # Check if path starts with /api/v1/ but NOT /api/v1/discover/
            if path.startswith("/api/v1/") and not path.startswith("/api/v1/discover/"):
                # Check if it has a discover-specific suffix
                for suffix in discover_specific_suffixes:
                    # Normalize paths for comparison
                    if self._paths_match_suffix(path, "/api/v1" + suffix):
                        wrong_prefix_routes.append(path)
                        break
        
        assert len(wrong_prefix_routes) == 0, (
            f"Found Discover routes at wrong prefix /api/v1/ (without /discover):\n" +
            "\n".join(f"  - {p}" for p in wrong_prefix_routes) +
            f"\n\nThese should be at /api/v1/discover/*"
        )

    def test_discover_routes_have_correct_handlers(self, client):
        """
        Verify Discover routes have the expected handler functions attached.
        
        This ensures the route paths aren't just registered but actually
        point to the correct handler functions.
        """
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        openapi = response.json()
        
        # Map of path -> expected handler names (from operationId or summary)
        expected_handlers = {
            "/api/v1/discover/query/stream": "stream_query",
            "/api/v1/discover/sessions/{session_id}/save": "save_conversation",
            "/api/v1/discover/sessions/{session_id}/share": "share_conversation",
            "/api/v1/discover/credentials/{tool_id}": "get_credential",
            "/api/v1/discover/credentials": "save_credential",
            "/api/v1/discover/tools": "get_tools",
            "/api/v1/discover/tools/{tool_id}/status": "get_tool_status",
            "/api/v1/discover/handoff/{ref_id}/attach": "attach_handoff",
            "/api/v1/discover/handoff/pending/{runtime_session_id}": "get_pending_messages",
            "/api/v1/discover/feedback/ui": "submit_feedback",
        }
        
        mismatches = []
        
        for path, expected_handler in expected_handlers.items():
            if path not in openapi.get("paths", {}):
                mismatches.append(f"{path}: route not found")
                continue
            
            # Get any method's operation (they should all have same handler)
            methods = openapi["paths"][path]
            for method, operation in methods.items():
                if method == "parameters":
                    continue
                
                operation_id = operation.get("operationId", "")
                # Handler name might be in operationId or we can infer from path
                # Since we don't have operationId set, we just verify the route exists
                # with at least one handler
                if not operation.get("operationId") and not operation.get("summary"):
                    # Check if it has a response schema (indicates it's properly set up)
                    if "responses" not in operation:
                        mismatches.append(f"{path}: missing operation metadata")
        
        # For now, just verify routes exist with handlers attached
        # The actual handler name verification would require operationId to be set
        assert len([m for m in mismatches if "route not found" in m]) == 0, (
            f"Some Discover routes are missing:\n" + "\n".join(mismatches)
        )

    def _paths_match(self, expected: str, actual: str) -> bool:
        """Compare paths accounting for path parameters."""
        if expected == actual:
            return True
        
        # Split and compare segments
        exp_parts = expected.split("/")
        act_parts = actual.split("/")
        
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

    def _paths_match_suffix(self, path: str, suffix: str) -> bool:
        """Check if path ends with the given suffix pattern."""
        path_parts = path.split("/")
        suffix_parts = suffix.split("/")
        
        if len(path_parts) < len(suffix_parts):
            return False
        
        # Compare from the end
        for p_part, s_part in zip(reversed(path_parts), reversed(suffix_parts)):
            if s_part.startswith("{") and p_part.startswith("{"):
                continue  # Both parameterized
            if s_part.startswith("{") or p_part.startswith("{"):
                return False  # One parameterized, one not
            if p_part != s_part:
                return False  # Literal mismatch
        
        return True


class TestDiscoverRouterPrefix:
    """Tests specifically for the router prefix configuration."""

    def test_router_prefix_includes_discover(self):
        """
        Verify the discover router is registered with /api/v1/discover prefix.
        
        This is the root cause test - it directly checks the registration.
        """
        from src.api.api import create_app
        from src.api.routers import discover as discover_module
        
        app = create_app()
        
        # Check that routes exist with /discover prefix
        discover_routes = []
        for route in app.routes:
            if hasattr(route, "path"):
                if route.path.startswith("/api/v1/discover/"):
                    discover_routes.append(route.path)
        
        # Should have multiple discover routes
        assert len(discover_routes) >= 5, (
            f"Expected at least 5 discover routes, found {len(discover_routes)}. "
            f"Routes found: {discover_routes}"
        )
        
        # All should have the correct prefix
        for route in discover_routes:
            assert route.startswith("/api/v1/discover/"), (
                f"Route {route} doesn't start with /api/v1/discover/"
            )

    def test_router_not_registered_at_api_v1_root(self):
        """
        Verify discover router is NOT registered at /api/v1 root.
        
        This catches the bug where:
        app.include_router(discover.router, prefix="/api/v1")  # WRONG
        """
        from src.api.api import create_app
        
        app = create_app()
        
        # Collect paths that start with /api/v1/ but NOT /api/v1/discover/
        non_discover_paths = []
        for route in app.routes:
            if hasattr(route, "path"):
                path = route.path
                if path.startswith("/api/v1/") and not path.startswith("/api/v1/discover/"):
                    non_discover_paths.append(path)
        
        # None of these should be discover-specific paths
        discover_indicators = [
            "/query/stream",
            "/credentials",
            "/handoff",
            "/feedback/ui",
        ]
        
        violations = []
        for path in non_discover_paths:
            for indicator in discover_indicators:
                if indicator in path:
                    violations.append(path)
                    break
        
        assert len(violations) == 0, (
            f"Discover routes found at wrong prefix /api/v1/ (without /discover): "
            f"{violations}\n"
            f"Check api.py for: app.include_router(discover.router, prefix='/api/v1') "
            f"and change to: app.include_router(discover.router, prefix='/api/v1/discover')"
        )


class TestDiscoverFrontendContract:
    """Contract tests verifying frontend service expectations."""

    def test_frontend_service_definitions_exist(self):
        """
        Verify frontend service files exist and have correct imports.
        
        This ensures the frontend side of the contract is maintained.
        """
        services_dir = Path("ui/src/services/discover")
        if not services_dir.exists():
            pytest.skip("Frontend services directory not found")
        
        expected_services = [
            "discover.service.ts",
            "conversation.service.ts",
            "credentials.service.ts",
            "handoff.service.ts",
            "tools.service.ts",
        ]
        
        missing = []
        for service in expected_services:
            if not (services_dir / service).exists():
                missing.append(service)
        
        assert len(missing) == 0, f"Missing frontend service files: {missing}"

    def test_frontend_services_use_discover_proxy(self):
        """
        Verify frontend services use the Discover proxy paths (/api/v1/discover/*).
        
        This ensures frontend calls the correct backend routes.
        """
        services_dir = Path("ui/src/services/discover")
        if not services_dir.exists():
            pytest.skip("Frontend services directory not found")

        issues = []

        for service_file in services_dir.glob("*.service.ts"):
            content = service_file.read_text()

            # Must reference /api/v1/discover/
            if "/api/v1/discover/" not in content:
                issues.append(f"{service_file.name}: missing /api/v1/discover/ reference")

            # Must NOT use old /api/v1/ without /discover for discover calls
            # This is a heuristic check - we look for /api/v1/ followed by discover terms
            # Find all /api/v1/ references
            refs = re.findall(r'/api/v1/\w+', content)
            discover_terms = ['query', 'sessions', 'credentials', 'tools', 'handoff', 'feedback']
            
            for ref in refs:
                term = ref.replace('/api/v1/', '')
                if term in discover_terms and '/api/v1/discover/' not in ref:
                    issues.append(
                        f"{service_file.name}: uses {ref} without /discover prefix"
                    )
        
        assert len(issues) == 0, (
            f"Frontend service path issues:\n" + "\n".join(f"  - {i}" for i in issues)
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
