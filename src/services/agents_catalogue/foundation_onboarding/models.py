"""
Pydantic models for Foundation Onboarding API

This module contains Pydantic models for request/response validation
and OpenAPI documentation generation.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# Database Configuration Models
# =============================================================================

class DatabaseConfig(BaseModel):
    """
    Configuration for database provisioning.
    
    Specifies the database type, version, and resource requirements
    for the new service's database.
    """
    
    db_type: str = Field(..., description="Type of database (postgres, mysql, mongodb, redis)")
    db_name: str = Field(..., description="Database name")
    
    @field_validator('db_type')
    @classmethod
    def validate_db_type(cls, v: str) -> str:
        """Validate database type is supported."""
        # TODO: Implement validation for supported database types
        valid_types = ["postgres", "mysql", "mongodb", "redis"]
        if v not in valid_types:
            raise ValueError(f"Database type must be one of: {', '.join(valid_types)}")
        return v


# =============================================================================
# Kubernetes Configuration Models
# =============================================================================

class KubernetesConfig(BaseModel):
    """
    Configuration for Kubernetes manifest generation.
    
    Specifies namespace, resource limits, replicas, and other
    Kubernetes-specific settings.
    """
  
    namespace: str = Field(..., description="Kubernetes namespace for the service")
    replicas: int = Field(default=2, description="Number of replicas")


# =============================================================================
# Spinnaker Configuration Models
# =============================================================================

class SpinnakerConfig(BaseModel):
    """
    Configuration for Spinnaker pipeline creation.
    
    Specifies deployment stages, environments, and pipeline settings.
    """
    
    pipeline_name: Optional[str] = Field(None, description="Custom pipeline name")
    environments: List[str] = Field(default=["dev", "stage", "prod"], description="Deployment environments")


# =============================================================================
# Kafka Configuration Models
# =============================================================================

class KafkaConfig(BaseModel):
    """
    Configuration for Kafka consumer and topic setup.
    
    Specifies topic names, consumer groups, and partition settings.
    """

    consumer_group: Optional[str] = Field(None, description="Consumer group name")
    topics: Optional[List[str]] = Field(None, description="List of topic names")


# =============================================================================
# Edge Gateway Configuration Models
# =============================================================================

class EdgeConfig(BaseModel):
    """
    Configuration for Edge gateway onboarding.
    
    Specifies routing rules, rate limits, and authentication settings.
    """
    
    routes: Optional[List[Dict[str, Any]]] = Field(None, description="Route configurations")


# =============================================================================
# Authorization Configuration Models
# =============================================================================

class AuthzConfig(BaseModel):
    """
    Configuration for Authorization (Authz) onboarding.
    
    Specifies roles, permissions, and access control settings.
    """
    
    roles: Optional[List[str]] = Field(None, description="Roles for the service")


# =============================================================================
# Monitoring Configuration Models
# =============================================================================

class MonitoringConfig(BaseModel):
    """
    Configuration for Monitoring and alerting setup.
    
    Specifies metrics, dashboards, and alerting rules.
    """
    
    dashboard_enabled: bool = Field(default=True, description="Whether to create Grafana dashboard")
    alerts_enabled: bool = Field(default=True, description="Whether to create alerting rules")


# =============================================================================
# Main Request/Response Models
# =============================================================================

class FoundationOnboardingRequest(BaseModel):
    """
    Foundation onboarding request model.
    
    Contains all configuration required to onboard a new service
    through the foundation onboarding workflow.
    """
    
    # Core service information
    service_name: str = Field(..., description="Name of the service to onboard")
    team_name: str = Field(..., description="Team owning the service")
    description: Optional[str] = Field(None, description="Service description")
    
    # Component configurations
    database_config: Optional[DatabaseConfig] = Field(None, description="Database configuration")
    kubernetes_config: KubernetesConfig = Field(..., description="Kubernetes configuration")
    spinnaker_config: Optional[SpinnakerConfig] = Field(None, description="Spinnaker pipeline configuration")
    kafka_config: Optional[KafkaConfig] = Field(None, description="Kafka configuration")
    edge_config: Optional[EdgeConfig] = Field(None, description="Edge gateway configuration")
    authz_config: Optional[AuthzConfig] = Field(None, description="Authorization configuration")
    monitoring_config: Optional[MonitoringConfig] = Field(None, description="Monitoring configuration")
    
    @field_validator('service_name')
    @classmethod
    def validate_service_name(cls, v: str) -> str:
        """Validate service name follows naming conventions."""
        v = v.strip()
        if not v:
            raise ValueError("Service name cannot be empty")
        return v


class FoundationOnboardingResponse(BaseModel):
    """
    Foundation onboarding response model.
    
    Contains the result of the onboarding workflow execution.
    """
    
    status: str = Field(..., description="Execution status (queued, completed, failed, partial_success)")
    message: str = Field(..., description="Human-readable message")
    task_id: Optional[str] = Field(None, description="Task identifier for background processing")
    execution_time: Optional[float] = Field(None, description="Execution time in seconds")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional execution metadata")
    
    # Step-specific results
    repo_url: Optional[str] = Field(None, description="Created repository URL")
    database_connection_string: Optional[str] = Field(None, description="Database connection string")
    spinnaker_pipeline_url: Optional[str] = Field(None, description="Spinnaker pipeline URL")
    monitoring_dashboard_url: Optional[str] = Field(None, description="Grafana dashboard URL")
    
    # Detailed step results
    steps_completed: Optional[List[str]] = Field(None, description="List of completed steps")
    steps_failed: Optional[List[str]] = Field(None, description="List of failed steps")
    pull_requests_created: Optional[List[Dict[str, str]]] = Field(None, description="Pull requests created")


class FoundationOnboardingErrorResponse(BaseModel):
    """
    Foundation onboarding error response model.
    
    Provides detailed error information for failed requests.
    """
    
    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Type of error")
    error_code: str = Field(..., description="Machine-readable error code")
    task_id: Optional[str] = Field(None, description="Task ID if available")
    validation_errors: Optional[List[str]] = Field(None, description="Detailed validation errors")
    suggestions: Optional[List[str]] = Field(None, description="Suggested actions to resolve the error")
    failed_step: Optional[str] = Field(None, description="Step where the failure occurred")

