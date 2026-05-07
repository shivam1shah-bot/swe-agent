"""
Service registry for agents catalogue.

This module provides dynamic service registration and discovery functionality.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Type, Callable
from datetime import datetime
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class ServiceMetrics:
    """Metrics for a registered service."""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_execution_time: float = 0.0
    last_execution: Optional[datetime] = None
    average_execution_time: float = 0.0
    error_rate: float = 0.0
    
    def update_execution(self, success: bool, execution_time: float):
        """Update metrics after a service execution."""
        self.total_executions += 1
        self.total_execution_time += execution_time
        self.last_execution = datetime.utcnow()
        
        if success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1
            
        # Update derived metrics
        self.average_execution_time = self.total_execution_time / self.total_executions
        self.error_rate = (self.failed_executions / self.total_executions) * 100 if self.total_executions > 0 else 0.0

@dataclass 
class ServiceRegistration:
    """Registration information for an agents catalogue service."""
    name: str
    service_class: Type
    instance: Any
    registered_at: datetime
    last_health_check: Optional[datetime] = None
    health_status: str = "unknown"
    metrics: ServiceMetrics = None
    description: str = ""
    capabilities: List[str] = None
    version: str = "1.0.0"
    
    def __post_init__(self):
        if self.metrics is None:
            self.metrics = ServiceMetrics()
        if self.capabilities is None:
            self.capabilities = []

class ServiceRegistry:
    """
    Enhanced service registry for agents catalogue with health monitoring and metrics.
    """
    
    def __init__(self):
        """Initialize the service registry."""
        self._services: Dict[str, ServiceRegistration] = {}
        self._health_check_interval = 300  # 5 minutes
        self._last_registry_health_check = None
        logger.info("Service registry initialized")
    
    def register(self, service_name: str, service_class: Type) -> None:
        """
        Register a service in the agents catalogue.
        
        Args:
            service_name: Unique name for the service
            service_class: Class implementing the service
            
        Raises:
            ValueError: If service name is already registered or invalid
        """
        try:
            # Validate service name
            if not service_name or not isinstance(service_name, str):
                raise ValueError("Service name must be a non-empty string")
            
            if service_name in self._services:
                logger.warning(f"Service '{service_name}' is already registered. Updating registration.")
            
            # Create service instance
            service_instance = service_class()
            
            # Monkey-patch execute()/async_execute() with Prometheus metrics
            # wrappers so every agent gets invocation counts, durations, and
            # success/failure rates automatically — no per-agent code changes.
            try:
                from types import MethodType
                from .metrics_wrapper import track_agent_execution, get_agent_name
                
                # Get agent name from service instance
                agent_name = get_agent_name(service_instance)
                
                # Wrap execute method with metrics tracking
                if hasattr(service_instance, 'execute'):
                    original_execute = service_instance.execute
                    # Get the unbound function from the bound method
                    unbound_execute = original_execute.__func__
                    wrapped_execute = track_agent_execution(agent_name, "sync", unbound_execute)
                    # Bind wrapper as an instance method (avoid losing `self`)
                    service_instance.execute = MethodType(wrapped_execute, service_instance)
                    logger.debug(f"Applied metrics tracking to execute() for service '{service_name}'")
                
                # Wrap async_execute method with metrics tracking
                if hasattr(service_instance, 'async_execute'):
                    original_async_execute = service_instance.async_execute
                    # Get the unbound function from the bound method
                    unbound_async_execute = original_async_execute.__func__
                    wrapped_async_execute = track_agent_execution(agent_name, "async", unbound_async_execute)
                    # Bind wrapper as an instance method (avoid losing `self`)
                    service_instance.async_execute = MethodType(wrapped_async_execute, service_instance)
                    logger.debug(f"Applied metrics tracking to async_execute() for service '{service_name}'")
            except Exception as e:
                logger.warning(f"Failed to apply metrics tracking to service '{service_name}': {e}")
                # Continue with registration even if metrics tracking fails
            
            # Extract service metadata
            description = getattr(service_instance, 'description', f"Agents catalogue service: {service_name}")
            capabilities = getattr(service_instance, 'capabilities', [])
            version = getattr(service_instance, 'version', '1.0.0')
            
            # Create registration
            registration = ServiceRegistration(
                name=service_name,
                service_class=service_class,
                instance=service_instance,
                registered_at=datetime.utcnow(),
                description=description,
                capabilities=capabilities,
                version=version
            )
            
            # Perform initial health check
            registration.health_status = self._check_service_health(registration)
            registration.last_health_check = datetime.utcnow()
            
            # Register the service
            self._services[service_name] = registration
            
            logger.info(f"Successfully registered service '{service_name}'", extra={
                "service_name": service_name,
                "service_class": service_class.__name__,
                "health_status": registration.health_status,
                "capabilities": capabilities,
                "version": version
            })
            
        except Exception as e:
            logger.error(f"Failed to register service '{service_name}': {str(e)}")
            raise ValueError(f"Service registration failed: {str(e)}")
    
    def get_service(self, service_name: str) -> Optional[Any]:
        """
        Get a service instance by name.
        
        Args:
            service_name: Name of the service to retrieve
            
        Returns:
            Service instance or None if not found
        """
        registration = self._services.get(service_name)
        if registration:
            # Update last access time and perform health check if needed
            self._maybe_check_service_health(registration)
            
            if registration.health_status == "healthy":
                return registration.instance
            else:
                logger.warning(f"Service '{service_name}' is not healthy: {registration.health_status}")
                return registration.instance  # Return anyway, let caller handle
        
        logger.warning(f"Service '{service_name}' not found in registry")
        return None
    
    def list_services(self) -> List[str]:
        """
        Get list of all registered service names.
        
        Returns:
            List of service names
        """
        return list(self._services.keys())
    
    def get_service_info(self, service_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Service information dictionary or None if not found
        """
        registration = self._services.get(service_name)
        if not registration:
            return None
        
        # Perform health check if needed
        self._maybe_check_service_health(registration)
        
        return {
            "name": registration.name,
            "description": registration.description,
            "capabilities": registration.capabilities,
            "version": registration.version,
            "class": registration.service_class.__name__,
            "registered_at": registration.registered_at.isoformat(),
            "health_status": registration.health_status,
            "last_health_check": registration.last_health_check.isoformat() if registration.last_health_check else None,
            "metrics": {
                "total_executions": registration.metrics.total_executions,
                "successful_executions": registration.metrics.successful_executions,
                "failed_executions": registration.metrics.failed_executions,
                "error_rate": registration.metrics.error_rate,
                "average_execution_time": registration.metrics.average_execution_time,
                "last_execution": registration.metrics.last_execution.isoformat() if registration.metrics.last_execution else None
            }
        }
    
    def get_all_services_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed information about all registered services.
        
        Returns:
            Dictionary mapping service names to their information
        """
        return {
            service_name: self.get_service_info(service_name)
            for service_name in self._services.keys()
        }
    
    def update_service_metrics(self, service_name: str, success: bool, execution_time: float) -> None:
        """
        Update execution metrics for a service.
        
        Args:
            service_name: Name of the service
            success: Whether the execution was successful
            execution_time: Time taken for execution in seconds
        """
        registration = self._services.get(service_name)
        if registration:
            registration.metrics.update_execution(success, execution_time)
            logger.debug(f"Updated metrics for service '{service_name}'", extra={
                "service_name": service_name,
                "success": success,
                "execution_time": execution_time,
                "total_executions": registration.metrics.total_executions,
                "error_rate": registration.metrics.error_rate
            })
        else:
            logger.warning(f"Cannot update metrics for unknown service '{service_name}'")
    
    def get_registry_health(self) -> Dict[str, Any]:
        """
        Get overall health status of the service registry.
        
        Returns:
            Health status dictionary
        """
        self._perform_registry_health_check()
        
        total_services = len(self._services)
        healthy_services = sum(1 for reg in self._services.values() if reg.health_status == "healthy")
        degraded_services = sum(1 for reg in self._services.values() if reg.health_status == "degraded")
        unhealthy_services = sum(1 for reg in self._services.values() if reg.health_status == "unhealthy")
        
        overall_status = "healthy"
        if unhealthy_services > 0:
            overall_status = "unhealthy"
        elif degraded_services > 0:
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "total_services": total_services,
            "healthy_services": healthy_services,
            "degraded_services": degraded_services,
            "unhealthy_services": unhealthy_services,
            "last_health_check": self._last_registry_health_check.isoformat() if self._last_registry_health_check else None,
            "service_details": {
                name: {
                    "status": reg.health_status,
                    "last_check": reg.last_health_check.isoformat() if reg.last_health_check else None
                }
                for name, reg in self._services.items()
            }
        }
    
    def get_registry_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated metrics for all services in the registry.
        
        Returns:
            Aggregated metrics dictionary
        """
        total_executions = sum(reg.metrics.total_executions for reg in self._services.values())
        total_successful = sum(reg.metrics.successful_executions for reg in self._services.values())
        total_failed = sum(reg.metrics.failed_executions for reg in self._services.values())
        total_time = sum(reg.metrics.total_execution_time for reg in self._services.values())
        
        overall_error_rate = (total_failed / total_executions * 100) if total_executions > 0 else 0.0
        overall_avg_time = (total_time / total_executions) if total_executions > 0 else 0.0
        
        # Service-specific metrics
        service_metrics = {}
        for name, reg in self._services.items():
            service_metrics[name] = {
                "executions": reg.metrics.total_executions,
                "success_rate": ((reg.metrics.successful_executions / reg.metrics.total_executions) * 100) if reg.metrics.total_executions > 0 else 0.0,
                "error_rate": reg.metrics.error_rate,
                "avg_execution_time": reg.metrics.average_execution_time,
                "last_execution": reg.metrics.last_execution.isoformat() if reg.metrics.last_execution else None
            }
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall": {
                "total_executions": total_executions,
                "successful_executions": total_successful,
                "failed_executions": total_failed,
                "overall_error_rate": overall_error_rate,
                "overall_avg_execution_time": overall_avg_time
            },
            "by_service": service_metrics,
            "registry": {
                "total_services": len(self._services),
                "active_services": sum(1 for reg in self._services.values() if reg.health_status == "healthy")
            }
        }
    
    def unregister(self, service_name: str) -> bool:
        """
        Unregister a service from the agents catalogue.
        
        Args:
            service_name: Name of the service to unregister
            
        Returns:
            True if service was unregistered, False if not found
        """
        if service_name in self._services:
            registration = self._services.pop(service_name)
            logger.info(f"Unregistered service '{service_name}'", extra={
                "service_name": service_name,
                "was_healthy": registration.health_status == "healthy",
                "total_executions": registration.metrics.total_executions
            })
            return True
        else:
            logger.warning(f"Cannot unregister unknown service '{service_name}'")
            return False
    
    def _check_service_health(self, registration: ServiceRegistration) -> str:
        """
        Check the health of a specific service.
        
        Args:
            registration: Service registration to check
            
        Returns:
            Health status string: "healthy", "degraded", or "unhealthy"
        """
        try:
            # Basic health check - ensure service instance exists and has required methods
            if not registration.instance:
                return "unhealthy"
            
            if not hasattr(registration.instance, 'execute'):
                logger.warning(f"Service '{registration.name}' missing execute method")
                return "degraded"
            
            # Check error rate
            if registration.metrics.total_executions > 10:  # Only check if we have enough data
                if registration.metrics.error_rate > 50:  # More than 50% errors
                    return "unhealthy"
                elif registration.metrics.error_rate > 20:  # More than 20% errors
                    return "degraded"
            
            # Check if service is responding in reasonable time
            if registration.metrics.average_execution_time > 600:  # More than 10 minutes average
                return "degraded"
            
            return "healthy"
            
        except Exception as e:
            logger.error(f"Health check failed for service '{registration.name}': {str(e)}")
            return "unhealthy"
    
    def _maybe_check_service_health(self, registration: ServiceRegistration) -> None:
        """
        Check service health if enough time has passed since last check.
        
        Args:
            registration: Service registration to potentially check
        """
        now = datetime.utcnow()
        
        # Check if we need to perform a health check
        if (not registration.last_health_check or 
            (now - registration.last_health_check).total_seconds() > self._health_check_interval):
            
            old_status = registration.health_status
            registration.health_status = self._check_service_health(registration)
            registration.last_health_check = now
            
            if old_status != registration.health_status:
                logger.info(f"Service '{registration.name}' health status changed: {old_status} -> {registration.health_status}")
    
    def _perform_registry_health_check(self) -> None:
        """Perform health check on all services if needed."""
        now = datetime.utcnow()
        
        if (not self._last_registry_health_check or 
            (now - self._last_registry_health_check).total_seconds() > self._health_check_interval):
            
            logger.info("Performing registry-wide health check")
            
            for registration in self._services.values():
                self._maybe_check_service_health(registration)
            
            self._last_registry_health_check = now
            logger.info(f"Completed registry health check for {len(self._services)} services")

# Global service registry instance
service_registry = ServiceRegistry()

def register_service(service_name: str) -> Callable:
    """
    Decorator for registering services in the agents catalogue.
    
    Args:
        service_name: Unique name for the service
        
    Returns:
        Decorator function
        
    Example:
        @register_service("my-service")
        class MyService(BaseAgentsCatalogueService):
            pass
    """
    def decorator(service_class: Type) -> Type:
        try:
            service_registry.register(service_name, service_class)
            logger.info(f"Registered service '{service_name}' via decorator")
        except Exception as e:
            logger.error(f"Failed to register service '{service_name}' via decorator: {str(e)}")
            # Don't raise exception here to avoid breaking service startup
        
        return service_class
    
    return decorator

def get_service_for_usecase(usecase_name: str) -> Optional[Any]:
    """
    Get a service instance for a specific use case.
    
    Args:
        usecase_name: Name of the use case
        
    Returns:
        Service instance or None if not found
    """
    return service_registry.get_service(usecase_name)

def update_service_metrics(service_name: str, success: bool, execution_time: float) -> None:
    """
    Update execution metrics for a service.
    
    Args:
        service_name: Name of the service
        success: Whether the execution was successful
        execution_time: Time taken for execution in seconds
    """
    service_registry.update_service_metrics(service_name, success, execution_time) 