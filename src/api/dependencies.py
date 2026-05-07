"""
Dependency injection for FastAPI routes.

This module provides dependency functions for injecting services and other
dependencies into API route handlers.
"""

from typing import Generator, Dict
from fastapi import Request, HTTPException, status, Depends

from sqlalchemy.orm import Session
from src.providers.database.session import session_factory
from src.providers.config_loader import get_config
from src.providers.database.provider import DatabaseProvider
from src.providers.logger import Logger
from src.providers.auth import BasicAuthProvider

from src.services.task_service import TaskService
from src.services.agents_catalogue_service import AgentsCatalogueService
from src.services.cache_service import CacheService


def get_db_session() -> Generator[Session, None, None]:
    """
    Get database session for dependency injection.
    
    Yields:
        Database session
    """
    session = session_factory.create_session()
    try:
        yield session
    finally:
        session.close()


def get_task_service(request: Request) -> TaskService:
    """
    Get task service instance from app state.
    
    Args:
        request: FastAPI request object to access app state
        
    Returns:
        TaskService instance from app state
        
    Raises:
        HTTPException: If service is not available
    """
    try:
        return request.app.state.task_service
    except AttributeError:
        config = get_config()
        db_provider = DatabaseProvider()

        if not db_provider.is_initialized():
            db_provider.initialize(config)

        return TaskService(config, db_provider)


def get_agents_catalogue_service(request: Request) -> AgentsCatalogueService:
    """
    Get agents catalogue service instance from app state.
    
    Args:
        request: FastAPI request object to access app state
        
    Returns:
        AgentsCatalogueService instance from app state
        
    Raises:
        HTTPException: If service is not available
    """
    try:
        return request.app.state.agents_catalogue_service
    except AttributeError:
        # Fallback for cases where app.state is not available (e.g., during testing)
        config = get_config()
        db_provider = DatabaseProvider()
        
        # Initialize if not already done
        if not db_provider.is_initialized():
            db_provider.initialize(config)
        
        return AgentsCatalogueService(config, db_provider)


def get_cache_service(request: Request) -> CacheService:
    """
    Get cache service instance from app state.
    
    Args:
        request: FastAPI request object to access app state
        
    Returns:
        CacheService instance from app state
        
    Raises:
        HTTPException: If service is not available
    """
    try:
        return request.app.state.cache_service
    except AttributeError:
        # Fallback for cases where app.state is not available (e.g., during testing)
        from src.providers.cache import cache_provider
        
        config = get_config()
        
        # Initialize cache provider if not already done
        if not cache_provider.is_initialized():
            cache_provider.initialize(config)
        
        return CacheService()


def get_logger(request: Request = None) -> Logger:
    """
    Get logger instance.
    
    Args:
        request: Optional FastAPI request object
        
    Returns:
        Logger instance
    """
    return Logger("API")


def get_current_user(request: Request) -> Dict[str, str]:
    """
    Get current authenticated user from request state.
    
    This dependency expects the BasicAuthMiddleware to have already
    validated the request and set current_user in request.state.
    
    Args:
        request: FastAPI request object with user info in state
        
    Returns:
        Dict containing user info (username, role)
        
    Raises:
        HTTPException: If user is not authenticated
    """
    if not hasattr(request.state, 'current_user') or not request.state.current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"}
        )
    
    return request.state.current_user


def require_admin(current_user: Dict[str, str] = Depends(get_current_user)) -> Dict[str, str]:
    """
    Require admin role for endpoint access.
    
    Args:
        current_user: Current authenticated user from get_current_user dependency
        
    Returns:
        User info if user has admin role
        
    Raises:
        HTTPException: If user doesn't have admin role
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
            headers={"error_type": "insufficient_permissions"}
        )
    
    return current_user


def get_auth_provider() -> BasicAuthProvider:
    """
    Get BasicAuthProvider instance for dependency injection.
    
    Returns:
        BasicAuthProvider instance
    """
    return BasicAuthProvider() 