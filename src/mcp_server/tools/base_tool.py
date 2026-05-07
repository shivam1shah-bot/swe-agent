"""
Base MCP Tool class providing common functionality for all tools.

Provides authentication, API integration, and common utilities for MCP tools.
"""

import json
import asyncio
from typing import Dict, Any, Optional, Union
from abc import ABC, abstractmethod
import httpx

from src.providers.logger import Logger
from src.providers.config_loader import get_config


class BaseMCPTool(ABC):
    """
    Abstract base class for all MCP tools.
    
    Provides common functionality including:
    - API endpoint calling
    - Authentication handling
    - Error management
    - Logging
    """
    
    def __init__(self, api_client=None):
        """
        Initialize the base tool.
        
        Args:
            api_client: HTTP client for calling SWE Agent API service.
                       If None, creates its own client (for backward compatibility).
        """
        self.logger = Logger(f"MCPTool.{self.__class__.__name__}")
        self.api_client = api_client
        
        # For backward compatibility, if no api_client provided, use old method
        if self.api_client is None:
            self.config = get_config()
            self._api_base_url = self._get_api_base_url()
    
    async def _call_with_api_client(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call API using the injected API client.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Optional request data
            
        Returns:
            API response data
        """
        try:
            if method.upper() == "GET":
                # Parse endpoint and query parameters
                base_endpoint = endpoint.split('?')[0]
                query_params = {}
                if '?' in endpoint:
                    query_string = endpoint.split('?', 1)[1]
                    for param in query_string.split('&'):
                        if '=' in param:
                            key, value = param.split('=', 1)
                            query_params[key] = value
                
                if base_endpoint == "/api/v1/health":
                    return await self.api_client.get_health()
                elif base_endpoint.startswith("/api/v1/tasks/") and base_endpoint.endswith("/logs"):
                    # Extract task_id from "/api/v1/tasks/{task_id}/logs"
                    task_id = base_endpoint.split("/")[4]
                    limit = int(query_params.get('limit', 50))
                    return await self.api_client.get_task_logs(task_id, limit=limit)
                elif base_endpoint.startswith("/api/v1/tasks/"):
                    # Extract task_id from "/api/v1/tasks/{task_id}"
                    task_id = base_endpoint.split("/")[4]
                    return await self.api_client.get_task(task_id)
                elif base_endpoint == "/api/v1/tasks":
                    # Handle list_tasks with query parameters
                    status = query_params.get('status')
                    limit = int(query_params.get('limit', 20))
                    return await self.api_client.list_tasks(status=status, limit=limit)
                elif base_endpoint == "/api/v1/agents-catalogue/services":
                    return await self.api_client.list_agents_catalogue_services()
                elif base_endpoint == "/api/v1/agents-catalogue/items":
                    # Handle agents catalogue items with query parameters
                    page = int(query_params.get('page', 1))
                    per_page = int(query_params.get('per_page', 20))
                    search = query_params.get('search')
                    type_filter = query_params.get('type')
                    lifecycle = query_params.get('lifecycle')
                    return await self.api_client.get_agents_catalogue_items(
                        page=page, per_page=per_page, search=search, type_filter=type_filter, lifecycle=lifecycle
                    )
                elif base_endpoint == "/api/v1/agents-catalogue/config":
                    return await self.api_client.get_agents_catalogue_config()
                else:
                    raise ValueError(f"Unsupported GET endpoint: {base_endpoint}")
            else:
                # For non-GET methods, use the generic request method
                return await self.api_client._make_request(method, endpoint, json_data=data)
        except Exception as e:
            self.logger.error("API client call failed", method=method, endpoint=endpoint, error=str(e))
            raise
        
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name - must be unique across all tools."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for AI models."""
        pass
    
    @property
    @abstractmethod
    def domain(self) -> str:
        """Tool domain (e.g., 'health', 'tasks', 'agents', 'admin')."""
        pass
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        """
        Input schema for the tool in JSON Schema format.
        Override in subclasses to define tool-specific parameters.
        """
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    @property
    def annotations(self) -> Optional[Dict[str, Any]]:
        """
        Optional annotations for the tool.
        Override in subclasses to provide additional metadata.
        """
        return None
    
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """
        Execute the tool with the given arguments.
        
        Args:
            **kwargs: Tool arguments
            
        Returns:
            Tool execution result
        """
        pass
    
    def _get_api_base_url(self) -> str:
        """
        Get the API base URL from configuration.
        
        Returns:
            API base URL
        """
        app_config = self.config.get("app", {})
        api_base_url = app_config.get("api_base_url", "http://localhost:8000")
        
        # Remove trailing slash
        return api_base_url.rstrip("/")
    
    async def call_api_endpoint(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Call an API endpoint and return the response.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint path (e.g., "/api/v1/health")
            data: Optional request data for POST/PUT requests
            headers: Optional additional headers
            timeout: Request timeout in seconds
            
        Returns:
            API response data
            
        Raises:
            Exception: If API call fails
        """
        # Use injected API client if available
        if self.api_client:
            return await self._call_with_api_client(method, endpoint, data)
        
        # Fallback to old method for backward compatibility
        url = f"{self._api_base_url}{endpoint}"
        
        # Prepare headers
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if headers:
            request_headers.update(headers)
        
        self.logger.debug("Calling API endpoint", method=method, url=url, data=data)
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method.upper() in ["GET", "DELETE"]:
                    response = await client.request(
                        method=method.upper(),
                        url=url,
                        headers=request_headers
                    )
                else:
                    response = await client.request(
                        method=method.upper(),
                        url=url,
                        headers=request_headers,
                        json=data
                    )
                
                # Check for HTTP errors
                response.raise_for_status()
                
                # Parse JSON response
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    # If response is not JSON, return text content
                    result = {"response": response.text}
                
                self.logger.debug("API call successful", method=method, url=url, status_code=response.status_code)
                return result
                
        except httpx.HTTPStatusError as e:
            self.logger.error("API call failed with HTTP error", method=method, url=url, status_code=e.response.status_code)
            
            # Try to get error details from response
            try:
                error_detail = e.response.json()
            except:
                error_detail = {"detail": e.response.text}
            
            raise Exception(f"API call failed: {e.response.status_code} - {error_detail}")
            
        except httpx.TimeoutException:
            self.logger.error("API call timed out", method=method, url=url, timeout=timeout)
            raise Exception(f"API call timed out after {timeout} seconds")
            
        except Exception as e:
            self.logger.error("API call failed", method=method, url=url, error=str(e))
            raise Exception(f"API call failed: {e}")
    
    async def stream_api_endpoint(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Stream from an API endpoint (for long-running operations).
        
        Args:
            method: HTTP method
            endpoint: API endpoint path
            data: Optional request data
            headers: Optional additional headers
            
        Yields:
            Streaming response data
        """
        url = f"{self._api_base_url}{endpoint}"
        
        # Prepare headers
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        if headers:
            request_headers.update(headers)
        
        self.logger.info("Starting API stream", method=method, url=url)
        
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    method=method.upper(),
                    url=url,
                    headers=request_headers,
                    json=data
                ) as response:
                    
                    response.raise_for_status()
                    
                    async for chunk in response.aiter_text():
                        if chunk.strip():
                            try:
                                # Try to parse as JSON
                                yield json.loads(chunk)
                            except json.JSONDecodeError:
                                # If not JSON, yield as text
                                yield {"data": chunk}
                                
        except Exception as e:
            self.logger.error("API streaming failed", method=method, url=url, error=str(e))
            raise Exception(f"API streaming failed: {e}")
    
    def validate_arguments(self, **kwargs) -> Dict[str, Any]:
        """
        Validate tool arguments against the input schema.
        
        Args:
            **kwargs: Tool arguments to validate
            
        Returns:
            Validated arguments
            
        Raises:
            ValueError: If validation fails
        """
        # Get required fields from schema
        required_fields = self.input_schema.get("required", [])
        properties = self.input_schema.get("properties", {})
        
        # Check required fields
        for field in required_fields:
            if field not in kwargs:
                raise ValueError(f"Required parameter '{field}' is missing")
        
        # Validate field types (basic validation)
        validated_args = {}
        for field, value in kwargs.items():
            if field in properties:
                field_schema = properties[field]
                field_type = field_schema.get("type")
                
                # Basic type validation
                if field_type and not self._validate_type(value, field_type):
                    raise ValueError(f"Parameter '{field}' must be of type {field_type}")
                
                validated_args[field] = value
            else:
                # Allow additional properties for flexibility
                validated_args[field] = value
        
        return validated_args
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """
        Basic type validation.
        
        Args:
            value: Value to validate
            expected_type: Expected JSON Schema type
            
        Returns:
            True if type is valid
        """
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "object": dict,
            "array": list
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type:
            return isinstance(value, expected_python_type)
        
        return True  # Allow unknown types
    
    def format_success_response(self, data: Any, message: Optional[str] = None) -> Dict[str, Any]:
        """
        Format a successful tool response.
        
        Args:
            data: Response data
            message: Optional success message
            
        Returns:
            Formatted response
        """
        response = {
            "success": True,
            "data": data
        }
        
        if message:
            response["message"] = message
            
        return response
    
    def format_error_response(self, error: str, code: Optional[str] = None) -> Dict[str, Any]:
        """
        Format an error tool response.
        
        Args:
            error: Error message
            code: Optional error code
            
        Returns:
            Formatted error response
        """
        response = {
            "success": False,
            "error": error
        }
        
        if code:
            response["error_code"] = code
            
        return response 