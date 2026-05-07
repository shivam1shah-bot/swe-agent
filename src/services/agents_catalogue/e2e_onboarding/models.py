"""
Pydantic models for E2E Onboarding API

This module contains Pydantic models for request/response validation
and OpenAPI documentation generation.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator, model_validator
import re
from urllib.parse import urlparse


class EphemeralDbConfig(BaseModel):
    """Configuration for ephemeral database setup."""
    
    db1_name: str = Field(..., description="Database name for the service")
    db1_username: str = Field(..., description="Database username")
    db1_seeding: Optional[bool] = Field(False, description="Whether to seed the database")
    db1_snapshot_path: Optional[str] = Field("", description="Path to database snapshot")
    requests_cpu: str = Field(..., description="CPU requests in format like '50m'")
    requests_memory: str = Field(..., description="Memory requests in format like '50Mi'")
    dns_policy: Optional[str] = Field("ClusterFirst", description="DNS policy for the pod")
    attach_volume: Optional[bool] = Field(False, description="Whether to attach persistent volume")
    node_selector: Optional[str] = Field("node.kubernetes.io/worker-database", description="Node selector for pod placement")
    type: str = Field(..., description="Database type (postgres, mysql, mongodb, redis)")
    version: str = Field(..., description="Database version")
    
    @field_validator('requests_cpu')
    @classmethod
    def validate_cpu(cls, v: str) -> str:
        if not re.match(r'^\d+m$', v):
            raise ValueError("CPU requests must be in format like '50m'")
        return v
    
    @field_validator('requests_memory')
    @classmethod
    def validate_memory(cls, v: str) -> str:
        if not re.match(r'^\d+Mi$', v):
            raise ValueError("Memory requests must be in format like '50Mi'")
        return v
    
    @field_validator('type')
    @classmethod
    def validate_db_type(cls, v: str) -> str:
        valid_types = ["postgres", "mysql", "mongodb", "redis"]
        if v not in valid_types:
            raise ValueError(f"Database type must be one of: {', '.join(valid_types)}")
        return v


class DatabaseEnvKeys(BaseModel):
    """Environment variable keys for database connection."""
    
    url: str = Field(..., description="Environment variable name for database URL")
    name: str = Field(..., description="Environment variable name for database name")
    username: str = Field(..., description="Environment variable name for database username")
    password: str = Field(..., description="Environment variable name for database password")


class DbMigration(BaseModel):
    """Database migration configuration."""
    
    db_image_prefix: str = Field(..., description="Docker image prefix for migration")
    migration_cmd: str = Field(..., description="Migration command (up/down)")
    
    @field_validator('migration_cmd')
    @classmethod
    def validate_migration_cmd(cls, v: str) -> str:
        valid_commands = ["up", "down"]
        if v not in valid_commands:
            raise ValueError(f"Migration command must be one of: {', '.join(valid_commands)}")
        return v


class Secrets(BaseModel):
    """Kubernetes secrets configuration."""
    
    name: str = Field(..., description="Kubernetes secret name")
    type: str = Field(..., description="Secret type (ephemeral/static)")
    
    @field_validator('type')
    @classmethod
    def validate_secret_type(cls, v: str) -> str:
        valid_types = ["ephemeral", "static"]
        if v not in valid_types:
            raise ValueError(f"Secret type must be one of: {', '.join(valid_types)}")
        return v


class ChartOverrideEntry(BaseModel):
    """Represents a single chart override mapping (key/value)."""

    key: str = Field(..., description="Chart value key")
    value: str = Field(..., description="Chart value override")

    @field_validator('key')
    @classmethod
    def validate_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Override key cannot be empty")
        return v.strip()

    @field_validator('value')
    @classmethod
    def validate_value(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Override value cannot be empty")
        return v.strip()


class ChartOverrides(BaseModel):
    """Helm chart value overrides."""

    image_pull_policy: Optional[str] = Field("Always", description="Image pull policy")
    replicas: Optional[ChartOverrideEntry] = Field(
        None,
        description="Replicas override mapping (key/value)",
    )
    node_selector: Optional[ChartOverrideEntry] = Field(
        None,
        description="Node selector override mapping (key/value)",
    )

    @field_validator('image_pull_policy')
    @classmethod
    def validate_image_pull_policy(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid_policies = ["Always", "IfNotPresent", "Never"]
            if v not in valid_policies:
                raise ValueError(f"Image pull policy must be one of: {', '.join(valid_policies)}")
        return v


class BranchNames(BaseModel):
    """Branch names for different repositories."""
    
    goutils: str = Field(..., description="Branch name for goutils repository")
    
    @model_validator(mode='before')
    @classmethod
    def validate_branch_names(cls, values):
        if isinstance(values, dict):
            # Ensure at least one branch name is provided
            if not values:
                raise ValueError("At least one branch name must be provided")
            
            # Validate that all values are non-empty strings
            for repo, branch in values.items():
                if not isinstance(branch, str) or not branch.strip():
                    raise ValueError(f"Branch name for {repo} must be a non-empty string")
        return values
    

class GoUtilsConfig(BaseModel):
    """Go-Utils configuration."""

    mode: str = Field(..., description="Execution mode for Go-Utils" )

    @field_validator('mode')
    @classmethod
    def validate_mode(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Go-Utils mode cannot be empty")
        return v


class E2ETestOrchestratorParams(BaseModel):
    """E2E test orchestrator parameters."""

    config_overrides: str = Field(..., description="Config overrides")


class E2EOnboardingRequest(BaseModel):
    """E2E onboarding request model."""
    service_name: str = Field(..., description="Name of the service to onboard")
    service_url: str = Field(..., description="URL of the service")
    namespace: str = Field(..., description="Kubernetes namespace for the service")
    commit_id: str = Field(..., description="Git commit ID of the service")
    use_ephemeral_db: bool = Field(True, description="Whether to use ephemeral database")
    ephemeral_db_config: Optional[EphemeralDbConfig] = Field(None, description="Ephemeral database configuration")
    database_env_keys: Optional[DatabaseEnvKeys] = Field(None, description="Database environment variable keys")
    db_migration: Optional[DbMigration] = Field(None, description="Database migration configuration")
    secrets: Secrets = Field(..., description="Kubernetes secrets configuration")
    chart_overrides: ChartOverrides = Field(..., description="Helm chart value overrides")
    branch_names: Dict[str, str] = Field(..., description="Branch names for different repositories")
    goutils_config: GoUtilsConfig = Field(..., description="Go-Utils configuration")
    e2e_test_orchestrator_params: E2ETestOrchestratorParams = Field(..., description="E2E test orchestrator parameters")
    
    @field_validator('service_name')
    @classmethod
    def validate_service_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Service name cannot be empty")
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Service name must contain only alphanumeric characters, hyphens, and underscores")
        if len(v) < 2:
            raise ValueError("Service name must be at least 2 characters long")
        if len(v) > 100:
            raise ValueError("Service name must be no more than 100 characters long")
        if v.startswith('-') or v.endswith('-') or v.startswith('_') or v.endswith('_'):
            raise ValueError("Service name cannot start or end with hyphen or underscore")
        return v
    
    @field_validator('service_url')
    @classmethod
    def validate_service_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Service URL cannot be empty")
        
        try:
            parsed = urlparse(v)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Service URL must be a valid URL with scheme and domain")
            if parsed.scheme not in ['http', 'https']:
                raise ValueError("Service URL must use http or https scheme")
        except Exception:
            raise ValueError("Service URL must be a valid URL")
        
        return v
    
    @field_validator('namespace')
    @classmethod
    def validate_namespace(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Namespace cannot be empty")
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError("Namespace must contain only lowercase letters, numbers, and hyphens")
        if len(v) > 63:
            raise ValueError("Namespace must be no more than 63 characters long")
        if v.startswith('-') or v.endswith('-'):
            raise ValueError("Namespace cannot start or end with hyphen")
        return v
    
    @field_validator('commit_id')
    @classmethod
    def validate_commit_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Commit ID cannot be empty")
        if not re.match(r'^[a-f0-9]{7,40}$', v.lower()):
            raise ValueError("Commit ID must be a valid Git commit SHA (7-40 hexadecimal characters)")
        return v
    
    @model_validator(mode='after')
    def validate_ephemeral_db_config(self):
        if self.use_ephemeral_db:
            if self.ephemeral_db_config is None:
                raise ValueError("ephemeral_db_config is required when use_ephemeral_db is true")
            if self.database_env_keys is None:
                raise ValueError("database_env_keys is required when use_ephemeral_db is true")
            if self.db_migration is None:
                raise ValueError("db_migration is required when use_ephemeral_db is true")
        return self
    
    @field_validator('branch_names')
    @classmethod
    def validate_branch_names_dict(cls, v: Dict[str, str]) -> Dict[str, str]:
        if not v:
            raise ValueError("Branch names cannot be empty")
        
        for repo, branch in v.items():
            if not isinstance(repo, str) or not repo.strip():
                raise ValueError("Repository names must be non-empty strings")
            if not isinstance(branch, str) or not branch.strip():
                raise ValueError(f"Branch name for {repo} must be a non-empty string")
        
        return v


class E2EOnboardingResponse(BaseModel):
    """E2E onboarding response model."""
    
    status: str = Field(..., description="Execution status")
    message: str = Field(..., description="Human-readable message")
    task_id: Optional[str] = Field(None, description="Task identifier for background processing")
    execution_time: Optional[float] = Field(None, description="Execution time in seconds")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional execution metadata")
    repositories_processed: Optional[List[str]] = Field(None, description="List of repositories processed")
    pull_requests_created: Optional[List[Dict[str, str]]] = Field(None, description="Pull requests created")
    database_config: Optional[Dict[str, Any]] = Field(None, description="Database configuration applied")
    auth_config: Optional[Dict[str, Any]] = Field(None, description="Authentication configuration applied")


class E2EOnboardingErrorResponse(BaseModel):
    """E2E onboarding error response model."""
    
    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Type of error")
    error_code: str = Field(..., description="Machine-readable error code")
    task_id: Optional[str] = Field(None, description="Task ID if available")
    validation_errors: Optional[List[str]] = Field(None, description="Detailed validation errors")
    suggestions: Optional[List[str]] = Field(None, description="Suggested actions")
