"""
E2E Onboarding Parameter Validator

This module contains the E2EOnboardingValidator class for validating parameters
for the E2E onboarding service.
"""

import json
import re
from typing import Any, Dict
from urllib.parse import urlparse

from .models import E2EOnboardingRequest


class E2EOnboardingValidator:
    """
    Validator class for E2E onboarding parameters.
    
    Provides comprehensive validation for all parameters used in the E2E onboarding workflow.
    """
    
    def __init__(self):
        pass
    
    def validate_service_name(self, value: Any) -> None:
        """Validate the service_name parameter."""
        if not value:
            raise ValueError("service_name is required and cannot be empty")
        
        if not isinstance(value, str):
            raise ValueError("service_name must be a string")
        
        service_name = value.strip()
        
        if not service_name:
            raise ValueError("service_name cannot be empty or only whitespace")

        if not re.match(r'^[a-zA-Z0-9_-]+$', service_name):
            raise ValueError(
                "service_name must contain only alphanumeric characters, hyphens, and underscores"
            )

        if len(service_name) < 2:
            raise ValueError("service_name must be at least 2 characters long")
        
        if len(service_name) > 100:
            raise ValueError("service_name must be no more than 100 characters long")
        
        if service_name.startswith('-') or service_name.endswith('-'):
            raise ValueError("service_name cannot start or end with a hyphen")
        
        if service_name.startswith('_') or service_name.endswith('_'):
            raise ValueError("service_name cannot start or end with an underscore")

    def validate_commit_id(self, value: Any) -> None:
        """Validate the commit_id parameter."""
        if not value:
            raise ValueError("commit_id is required and cannot be empty")
        
        if not isinstance(value, str):
            raise ValueError("commit_id must be a string")
        
        commit_id = value.strip()
        
        if not commit_id:
            raise ValueError("commit_id cannot be empty or only whitespace")
        
        # Git commit SHA validation (7-40 characters, hexadecimal)
        if not re.match(r'^[a-f0-9]{7,40}$', commit_id.lower()):
            raise ValueError("commit_id must be a valid Git commit SHA (7-40 hexadecimal characters)")

    def validate_service_url(self, value: Any) -> None:
        """Validate the service_url parameter."""
        if not value:
            raise ValueError("service_url is required and cannot be empty")

        if not isinstance(value, str):
            raise ValueError("service_url must be a string")

        url = value.strip()

        if not url:
            raise ValueError("service_url cannot be empty or only whitespace")

        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("service_url must be a valid URL with scheme and domain")

            if parsed.scheme not in ['http', 'https']:
                raise ValueError("service_url must use http or https scheme")
        except Exception:
            raise ValueError("service_url must be a valid URL")

    def validate_namespace(self, value: Any) -> None:
        """Validate the namespace parameter."""
        if not value:
            raise ValueError("namespace is required and cannot be empty")

        if not isinstance(value, str):
            raise ValueError("namespace must be a string")

        namespace = value.strip()

        if not namespace:
            raise ValueError("namespace cannot be empty or only whitespace")

        if not re.match(r'^[a-z0-9-]+$', namespace):
            raise ValueError("namespace must contain only lowercase letters, numbers, and hyphens")

        if len(namespace) > 63:
            raise ValueError("namespace must be no more than 63 characters long")

        if namespace.startswith('-') or namespace.endswith('-'):
            raise ValueError("namespace cannot start or end with a hyphen")

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate parameters for E2E onboarding using the full validation flow."""
        if not isinstance(parameters, dict):
            raise ValueError("Parameters must be a dictionary")

        return self.validate_full_onboarding_parameters(parameters)

    def validate_full_onboarding_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        required_params = {
            "service_name",
            "service_url",
            "namespace",
            "commit_id",
            "use_ephemeral_db",
            "secrets",
            "chart_overrides",
            "branch_names",
            "e2e_test_orchestrator_params",
        }

        missing = [key for key in required_params if key not in parameters]
        if missing:
            raise ValueError(f"Missing required parameter(s): {', '.join(sorted(missing))}")

        self.validate_service_name(parameters["service_name"])
        self.validate_service_url(parameters["service_url"])
        self.validate_namespace(parameters["namespace"])
        self.validate_commit_id(parameters["commit_id"])

        use_ephemeral_db = bool(parameters.get("use_ephemeral_db"))

        if use_ephemeral_db:
            if "ephemeral_db_config" not in parameters or parameters["ephemeral_db_config"] is None:
                raise ValueError("ephemeral_db_config is required when use_ephemeral_db is true")
            self._validate_ephemeral_db_config(parameters["ephemeral_db_config"])

            if "database_env_keys" not in parameters or parameters["database_env_keys"] is None:
                raise ValueError("database_env_keys is required when use_ephemeral_db is true")
            self._validate_database_env_keys(parameters["database_env_keys"])

            self._validate_db_migration(parameters["db_migration"])

        self._validate_secrets(parameters["secrets"])
        self._validate_chart_overrides(parameters["chart_overrides"])
        self._validate_branch_names(parameters["branch_names"])

        self._validate_e2e_test_orchestrator_params(parameters["e2e_test_orchestrator_params"])

        E2EOnboardingRequest(**parameters)
        return parameters

    def _validate_ephemeral_db_config(self, value: Dict[str, Any]) -> None:
        required_fields = [
            "db1_name",
            "db1_username",
            "requests_cpu",
            "requests_memory",
            "type",
            "version",
        ]

        for field in required_fields:
            if field not in value:
                raise ValueError(f"ephemeral_db_config.{field} is required")

        if not isinstance(value["db1_name"], str) or not value["db1_name"].strip():
            raise ValueError("ephemeral_db_config.db1_name must be a non-empty string")

        if not isinstance(value["db1_username"], str) or not value["db1_username"].strip():
            raise ValueError("ephemeral_db_config.db1_username must be a non-empty string")

        cpu = value["requests_cpu"]
        if not isinstance(cpu, str) or not re.match(r'^\d+m$', cpu):
            raise ValueError("ephemeral_db_config.requests_cpu must be in format like '50m'")

        memory = value["requests_memory"]
        if not isinstance(memory, str) or not re.match(r'^\d+Mi$', memory):
            raise ValueError("ephemeral_db_config.requests_memory must be in format like '50Mi'")

        db_type = value["type"]
        valid_db_types = ["postgres", "mysql", "mongodb", "redis"]
        if db_type not in valid_db_types:
            raise ValueError(f"ephemeral_db_config.type must be one of: {', '.join(valid_db_types)}")

        version = value["version"]
        if not isinstance(version, str) or not version.strip():
            raise ValueError("ephemeral_db_config.version must be a non-empty string")

    def _validate_database_env_keys(self, value: Dict[str, Any]) -> None:
        required_fields = ["url", "name", "username", "password"]
        for field in required_fields:
            if field not in value:
                raise ValueError(f"database_env_keys.{field} is required")
            if not isinstance(value[field], str) or not value[field].strip():
                raise ValueError(f"database_env_keys.{field} must be a non-empty string")

    def _validate_db_migration(self, value: Dict[str, Any]) -> None:
        required_fields = ["db_image_prefix", "migration_cmd"]
        for field in required_fields:
            if field not in value:
                raise ValueError(f"db_migration.{field} is required")

        if not isinstance(value["db_image_prefix"], str) or not value["db_image_prefix"].strip():
            raise ValueError("db_migration.db_image_prefix must be a non-empty string")

        if value["migration_cmd"] not in {"up", "down"}:
            raise ValueError("db_migration.migration_cmd must be one of: up, down")

    def _validate_secrets(self, value: Dict[str, Any]) -> None:
        required_fields = ["name", "type"]
        for field in required_fields:
            if field not in value:
                raise ValueError(f"secrets.{field} is required")

        if not isinstance(value["name"], str) or not value["name"].strip():
            raise ValueError("secrets.name must be a non-empty string")

        if value["type"] not in {"ephemeral", "static"}:
            raise ValueError("secrets.type must be either 'ephemeral' or 'static'")

    def _validate_chart_overrides(self, value: Dict[str, Any]) -> None:
        if not isinstance(value, dict):
            raise ValueError("chart_overrides must be a dictionary")

        if "image_pull_policy" in value:
            if value["image_pull_policy"] not in {"Always", "IfNotPresent", "Never"}:
                raise ValueError("chart_overrides.image_pull_policy must be one of: Always, IfNotPresent, Never")

        for field in ["replicas", "node_selector"]:
            if field in value and value[field] is not None:
                mapping = value[field]
                if not isinstance(mapping, dict):
                    raise ValueError(f"chart_overrides.{field} must be an object with key and value")
                if "key" not in mapping or "value" not in mapping:
                    raise ValueError(f"chart_overrides.{field} must include both 'key' and 'value'")
                if not isinstance(mapping["key"], str) or not mapping["key"].strip():
                    raise ValueError(f"chart_overrides.{field}.key must be a non-empty string")
                if not isinstance(mapping["value"], str) or not mapping["value"].strip():
                    raise ValueError(f"chart_overrides.{field}.value must be a non-empty string")

    def _validate_branch_names(self, value: Dict[str, Any]) -> None:
        if not isinstance(value, dict):
            raise ValueError("branch_names must be a dictionary")

        if not value:
            raise ValueError("branch_names cannot be empty")

        for repo, branch in value.items():
            if not isinstance(repo, str) or not repo.strip():
                raise ValueError("branch_names keys must be non-empty strings")
            if not isinstance(branch, str) or not branch.strip():
                raise ValueError(f"branch_names.{repo} must be a non-empty string")

    def _validate_e2e_test_orchestrator_params(self, value: Dict[str, Any]) -> None:

        additional_params = value.get("additional_argo_params")
        if additional_params is not None:
            if isinstance(additional_params, str):
                try:
                    additional_params = json.loads(additional_params)
                except json.JSONDecodeError:
                    raise ValueError("e2e_test_orchestrator_params.additional_argo_params must be valid JSON")

            if not isinstance(additional_params, dict):
                raise ValueError("e2e_test_orchestrator_params.additional_argo_params must be a dictionary or JSON string")

            for key, val in additional_params.items():
                if not isinstance(key, str) or not key.strip():
                    raise ValueError("Keys in e2e_test_orchestrator_params.additional_argo_params must be non-empty strings")
                if not isinstance(val, (str, int, float, bool)):
                    raise ValueError("Values in e2e_test_orchestrator_params.additional_argo_params must be primitive types")

        config_overrides = value.get("config_overrides")
        if config_overrides is None:
            raise ValueError("e2e_test_orchestrator_params.config_overrides is required")
        if not isinstance(config_overrides, str):
            raise ValueError("e2e_test_orchestrator_params.config_overrides must be a string")


# Global instance for validation
validator = E2EOnboardingValidator()

# Module-level validation functions for validator discovery system
def validate_service_name(value: Any) -> Any:
    """Validate service name parameter."""
    validator.validate_service_name(value)
    return value

def validate_service_url(value: Any) -> Any:
    """Validate service URL parameter.""" 
    validator.validate_service_url(value)
    return value

def validate_namespace(value: Any) -> Any:
    """Validate namespace parameter."""
    validator.validate_namespace(value)
    return value

def validate_commit_id(value: Any) -> Any:
    """Validate commit ID parameter."""
    validator.validate_commit_id(value)
    return value
