"""
Rate Limiter for MCP tool execution.

Implements rate limiting to prevent abuse and DoS attacks on MCP tools.
"""

import time
from typing import Dict, Tuple, Any
from collections import defaultdict, deque
from dataclasses import dataclass

from src.providers.logger import Logger


@dataclass
class RateLimitRule:
    """Rate limit rule configuration."""
    max_requests: int
    time_window: int = None  # seconds
    window_seconds: int = None  # seconds (alternative name for backward compatibility)
    tool_specific: bool = False
    burst_allowance: int = 0  # additional requests allowed in burst
    
    def __post_init__(self):
        """Set time_window from window_seconds if provided."""
        if self.window_seconds is not None and self.time_window is None:
            self.time_window = self.window_seconds
        elif self.time_window is None and self.window_seconds is None:
            raise ValueError("Either time_window or window_seconds must be provided")
        elif self.window_seconds is None:
            self.window_seconds = self.time_window


class MCPRateLimiter:
    """
    Rate limiter for MCP tool execution.
    
    Implements sliding window rate limiting with per-client and per-tool limits.
    """
    
    def __init__(self):
        """Initialize rate limiter."""
        self.logger = Logger("MCPRateLimiter")
        
        # Client request history: client_id -> tool_name -> deque of timestamps
        self.request_history: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(deque))
        
        # Rate limit rules
        self.rules = self._get_default_rules()
        
        # Cleanup interval
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes
    
    def _get_default_rules(self) -> Dict[str, RateLimitRule]:
        """
        Get default rate limit rules.
        
        Returns:
            Dictionary of rule name to RateLimitRule
        """
        return {
            # General MCP request rate limit
            "mcp_request": RateLimitRule(
                max_requests=100,
                time_window=60  # 100 requests per minute
            ),
            
            # MCP stream creation rate limit
            "mcp_stream": RateLimitRule(
                max_requests=10,
                time_window=60  # 10 streams per minute
            ),
            
            # Tool execution rate limits
            "tool_execution": RateLimitRule(
                max_requests=50,
                time_window=60  # 50 tool executions per minute
            ),
            
            # Health tool specific (more permissive)
            "health_tool": RateLimitRule(
                max_requests=100,
                time_window=60,
                tool_specific=True
            ),
            
            # Admin tool specific (more restrictive)
            "admin_tool": RateLimitRule(
                max_requests=20,
                time_window=60,
                tool_specific=True
            ),
            
            # Long-running operations (very restrictive)
            "long_running": RateLimitRule(
                max_requests=5,
                time_window=300  # 5 operations per 5 minutes
            )
        }
    
    def check_rate_limit(self, client_id: str, operation: str, tool_name: str = None) -> bool:
        """
        Check if a request is within rate limits.
        
        Args:
            client_id: Client identifier
            operation: Operation type (e.g., "mcp_request", "tool_execution")
            tool_name: Optional tool name for tool-specific limits
            
        Returns:
            True if request is allowed
        """
        current_time = time.time()
        
        # Clean up old entries periodically
        self._cleanup_if_needed(current_time)
        
        # Get applicable rule
        rule = self._get_applicable_rule(operation, tool_name)
        if not rule:
            # No rule found, allow request
            return True
        
        # Get request history for this client and operation
        operation_key = f"{operation}:{tool_name}" if tool_name else operation
        request_times = self.request_history[client_id][operation_key]
        
        # Remove old requests outside the time window
        cutoff_time = current_time - rule.time_window
        while request_times and request_times[0] < cutoff_time:
            request_times.popleft()
        
        # Check if we're within the limit
        if len(request_times) >= rule.max_requests:
            self.logger.warning(
                "Rate limit exceeded",
                client_id=client_id,
                operation=operation,
                tool_name=tool_name,
                request_count=len(request_times),
                max_requests=rule.max_requests,
                time_window=rule.time_window
            )
            return False
        
        # Record this request
        request_times.append(current_time)
        
        self.logger.debug(
            "Rate limit check passed",
            client_id=client_id,
            operation=operation,
            tool_name=tool_name,
            request_count=len(request_times),
            max_requests=rule.max_requests
        )
        
        return True
    
    def _get_applicable_rule(self, operation: str, tool_name: str = None) -> RateLimitRule:
        """
        Get the applicable rate limit rule for an operation.
        
        Args:
            operation: Operation type
            tool_name: Optional tool name
            
        Returns:
            Applicable RateLimitRule or None
        """
        # Check for tool-specific rules first
        if tool_name:
            # Check for domain-specific rules
            if tool_name.startswith("overall_health"):
                return self.rules.get("health_tool")
        
        # Check for operation-specific rules
        return self.rules.get(operation)
    
    def get_rate_limit_status(self, client_id: str, operation: str = None, tool_name: str = None) -> Dict[str, Any]:
        """
        Get current rate limit status for a client.
        
        Args:
            client_id: Client identifier
            operation: Operation type (optional - if None, returns overall status)
            tool_name: Optional tool name
            
        Returns:
            Dictionary with rate limit status
        """
        current_time = time.time()
        
        # If no operation specified, return overall status
        if operation is None:
            total_requests = 0
            client_operations = self.request_history.get(client_id, {})
            
            for operation_key, request_times in client_operations.items():
                # Clean up old requests for this operation
                while request_times and request_times[0] < (current_time - 300):  # 5 minute window
                    request_times.popleft()
                total_requests += len(request_times)
            
            return {
                "limited": False,
                "total_requests": total_requests,
                "operations": len(client_operations),
                "requests_made": total_requests  # For backward compatibility
            }
        
        rule = self._get_applicable_rule(operation, tool_name)
        
        if not rule:
            return {
                "limited": False,
                "message": "No rate limit applied"
            }
        
        operation_key = f"{operation}:{tool_name}" if tool_name else operation
        request_times = self.request_history[client_id][operation_key]
        
        # Remove old requests
        cutoff_time = current_time - rule.time_window
        while request_times and request_times[0] < cutoff_time:
            request_times.popleft()
        
        current_count = len(request_times)
        remaining = max(0, rule.max_requests - current_count)
        
        # Calculate reset time
        reset_time = None
        if request_times:
            reset_time = request_times[0] + rule.time_window
        
        return {
            "limited": current_count >= rule.max_requests,
            "current_count": current_count,
            "max_requests": rule.max_requests,
            "time_window": rule.time_window,
            "remaining": remaining,
            "reset_time": reset_time
        }
    
    def _cleanup_if_needed(self, current_time: float):
        """
        Clean up old entries if needed.
        
        Args:
            current_time: Current timestamp
        """
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        cleaned_entries = 0
        
        # Clean up old request history
        for client_id in list(self.request_history.keys()):
            client_history = self.request_history[client_id]
            
            for operation_key in list(client_history.keys()):
                request_times = client_history[operation_key]
                
                # Find the most restrictive time window
                max_window = max(rule.time_window for rule in self.rules.values())
                cutoff_time = current_time - max_window
                
                # Remove old requests
                original_length = len(request_times)
                while request_times and request_times[0] < cutoff_time:
                    request_times.popleft()
                
                cleaned_entries += original_length - len(request_times)
                
                # Remove empty deques
                if not request_times:
                    del client_history[operation_key]
            
            # Remove empty client histories
            if not client_history:
                del self.request_history[client_id]
        
        self._last_cleanup = current_time
        
        if cleaned_entries > 0:
            self.logger.info("Cleaned up rate limiter entries", count=cleaned_entries)
    
    def cleanup_expired_entries(self):
        """Force cleanup of expired entries."""
        self._cleanup_if_needed(time.time())
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get rate limiter statistics.
        
        Returns:
            Dictionary with statistics
        """
        current_time = time.time()
        
        # Count active clients and requests
        active_clients = len(self.request_history)
        total_requests = 0
        
        for client_history in self.request_history.values():
            for request_times in client_history.values():
                total_requests += len(request_times)
        
        return {
            "active_clients": active_clients,
            "total_tracked_requests": total_requests,
            "rules_count": len(self.rules),
            "last_cleanup": self._last_cleanup,
            "timestamp": current_time
        }
    
    def add_rule(self, name: str, rule: RateLimitRule):
        """
        Add a custom rate limit rule.
        
        Args:
            name: Rule name
            rule: RateLimitRule configuration
        """
        self.rules[name] = rule
        self.logger.info("Added rate limit rule", name=name, max_requests=rule.max_requests, time_window=rule.time_window)
    
    def remove_rule(self, name: str) -> bool:
        """
        Remove a rate limit rule.
        
        Args:
            name: Rule name to remove
            
        Returns:
            True if rule was removed
        """
        if name in self.rules:
            del self.rules[name]
            self.logger.info("Removed rate limit rule", name=name)
            return True
        return False 