"""
HTTP Client for SWE Agent API Service.

This module provides a comprehensive HTTP client for the MCP service to communicate
with the SWE Agent API service. All MCP tools use this client to proxy calls to
the actual business logic in the API service.
"""

import httpx
import asyncio
import base64
from typing import Dict, Any, Optional, List
from ..config.settings import MCPSettings, get_mcp_settings


class APIClientError(Exception):
    """Base exception for API client errors."""
    pass


class APIConnectionError(APIClientError):
    """Exception raised when API service is unreachable."""
    pass


class APIAuthenticationError(APIClientError):
    """Exception raised when authentication fails."""
    pass


class SWEAgentAPIClient:
    """
    HTTP client for calling SWE Agent API service.
    
    This client handles all communication between the MCP service and the
    SWE Agent API service, including authentication, retries, and error handling.
    """
    
    def __init__(self, settings: Optional[MCPSettings] = None):
        """
        Initialize the API client.
        
        Args:
            settings: MCP settings. If None, uses global settings.
        """
        self.settings = settings or get_mcp_settings()
        self.base_url = self.settings.api_base_url.rstrip('/')
        
        # Create HTTP client with proper configuration
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SWE-Agent-MCP/1.0.0",
            "Origin": "http://localhost:28003"  # For CORS
        }
        
        # Add authentication if enabled
        if self.settings.auth_enabled and self.settings.auth_password:
            credentials = f"{self.settings.auth_username}:{self.settings.auth_password}"
            encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
            headers["Authorization"] = f"Basic {encoded_credentials}"
        
        self.client = httpx.AsyncClient(
            timeout=self.settings.api_timeout,
            headers=headers
        )
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        retries: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (will be prefixed with base_url)
            params: Query parameters
            json_data: JSON body data
            retries: Number of retries (defaults to settings.api_retries)
            
        Returns:
            JSON response data
            
        Raises:
            APIConnectionError: If service is unreachable
            APIAuthenticationError: If authentication fails
            APIClientError: For other API errors
        """
        retries = retries or self.settings.api_retries
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(retries + 1):
            try:
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data
                )
                
                # Handle authentication errors
                if response.status_code == 401:
                    raise APIAuthenticationError("Authentication failed with API service")
                
                # Handle other client errors
                if response.status_code >= 400:
                    error_detail = response.text
                    try:
                        error_json = response.json()
                        error_detail = error_json.get("detail", error_detail)
                    except:
                        pass
                    raise APIClientError(f"API request failed: {response.status_code} - {error_detail}")
                
                # Success - return JSON data
                return response.json()
                
            except httpx.ConnectError as e:
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
                raise APIConnectionError(f"Cannot connect to API service at {self.base_url}: {e}")
            
            except httpx.TimeoutException as e:
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise APIConnectionError(f"API request timeout: {e}")
            
            except (APIAuthenticationError, APIClientError):
                # Don't retry auth errors or client errors
                raise
            
            except Exception as e:
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise APIClientError(f"Unexpected error calling API: {e}")
    
    async def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request."""
        return await self._make_request("GET", endpoint, params=params)
    
    async def _post(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make POST request."""
        return await self._make_request("POST", endpoint, json_data=json_data)
    
    # Health endpoints
    async def get_health(self) -> Dict[str, Any]:
        """Call API health endpoint."""
        return await self._get("/api/v1/health")
    
    # Task endpoints
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Call API get task endpoint."""
        return await self._get(f"/api/v1/tasks/{task_id}")
    
    async def list_tasks(
        self, 
        status: Optional[str] = None, 
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Call API list tasks endpoint."""
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        return await self._get("/api/v1/tasks", params=params)
    
    async def get_task_logs(self, task_id: str, limit: int = 50) -> Dict[str, Any]:
        """Call API get task execution logs endpoint."""
        params = {"limit": limit}
        return await self._get(f"/api/v1/tasks/{task_id}/logs", params=params)
    
    # Agents catalogue endpoints
    async def list_agents_catalogue_services(self) -> Dict[str, Any]:
        """Call API agents catalogue services endpoint."""
        return await self._get("/api/v1/agents-catalogue/services")
    
    async def get_agents_catalogue_items(
        self,
        page: int = 1,
        per_page: int = 20,
        search: Optional[str] = None,
        type_filter: Optional[str] = None,
        lifecycle: Optional[str] = None
    ) -> Dict[str, Any]:
        """Call API agents catalogue items endpoint."""
        params = {
            "page": page,
            "per_page": per_page
        }
        if search:
            params["search"] = search
        if type_filter:
            params["type"] = type_filter
        if lifecycle:
            params["lifecycle"] = lifecycle
        
        return await self._get("/api/v1/agents-catalogue/items", params=params)
    
    async def get_agents_catalogue_config(self) -> Dict[str, Any]:
        """Call API agents catalogue config endpoint."""
        return await self._get("/api/v1/agents-catalogue/config")
    
    # Admin endpoints (if needed)
    async def get_admin_status(self) -> Dict[str, Any]:
        """Call API admin status endpoint."""
        return await self._get("/api/v1/admin/status")
    
    async def test_connection(self) -> bool:
        """
        Test connection to API service.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            await self.get_health()
            return True
        except Exception:
            return False
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close() 