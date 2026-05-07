"""
Foundation Onboarding Parameter Validator

This module contains the FoundationOnboardingValidator class for validating
parameters for the foundation onboarding service.
"""

import re
from typing import Any, Dict, List

from .models import FoundationOnboardingRequest


class FoundationOnboardingValidator:
    """
    Validator class for Foundation Onboarding parameters.
    
    Provides comprehensive validation for all parameters used in the
    foundation onboarding workflow including service info, database config,
    Kubernetes settings, and all other component configurations.
    """
    
    def __init__(self):
        """Initialize the validator."""
        pass
    
    def validate_service_name(self, value: Any) -> None:
        """
        Validate the service_name parameter.

        Args:
            value: Service name to validate

        Raises:
            ValueError: If validation fails
        """
        # TODO: Implement service name validation
        # - Check not empty
        # - Check is string type
        # - Check alphanumeric with hyphens only
        # - Check length limits (2-63 characters)
        # - Check doesn't start/end with hyphen
        # - Check for reserved names
        
        if not value:
            raise ValueError("service_name is required and cannot be empty")
        
        if not isinstance(value, str):
            raise ValueError("service_name must be a string")
        
        service_name = value.strip()
        
        if not service_name:
            raise ValueError("service_name cannot be empty or only whitespace")

        if not re.match(r'^[a-zA-Z0-9-]+$', service_name):
            raise ValueError(
                "service_name must contain only alphanumeric characters and hyphens"
            )

        if len(service_name) < 2:
            raise ValueError("service_name must be at least 2 characters long")
        
        if len(service_name) > 63:
            raise ValueError("service_name must be no more than 63 characters long")
        
        if service_name.startswith('-') or service_name.endswith('-'):
            raise ValueError("service_name cannot start or end with a hyphen")

    def validate_team_name(self, value: Any) -> None:
        """
        Validate the team_name parameter.

        Args:
            value: Team name to validate

        Raises:
            ValueError: If validation fails
        """
        # TODO: Implement team name validation
        # - Check not empty
        # - Check is string type
        # - Check valid format
        
        if not value:
            raise ValueError("team_name is required and cannot be empty")
        
        if not isinstance(value, str):
            raise ValueError("team_name must be a string")

    def validate_namespace(self, value: Any) -> None:
        """
        Validate the Kubernetes namespace parameter.

        Args:
            value: Namespace to validate

        Raises:
            ValueError: If validation fails
        """
        # TODO: Implement namespace validation
        # - Check not empty
        # - Check lowercase letters, numbers, and hyphens only
        # - Check length limit (63 characters)
        # - Check doesn't start/end with hyphen
        
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

    def validate_database_config(self, value: Dict[str, Any]) -> None:
        """
        Validate database configuration.

        Args:
            value: Database configuration dictionary

        Raises:
            ValueError: If validation fails
        """
        # TODO: Implement database config validation
        # - Validate db_type is supported
        # - Validate db_name format
        # - Validate resource specifications
        # - Validate version string
        
        if not isinstance(value, dict):
            raise ValueError("database_config must be a dictionary")
        
        # Required fields
        required_fields = ["db_type", "db_name"]
        for field in required_fields:
            if field not in value:
                raise ValueError(f"database_config.{field} is required")
        
        # Validate db_type
        valid_db_types = ["postgres", "mysql", "mongodb", "redis"]
        if value["db_type"] not in valid_db_types:
            raise ValueError(f"database_config.db_type must be one of: {', '.join(valid_db_types)}")

    def validate_kubernetes_config(self, value: Dict[str, Any]) -> None:
        """
        Validate Kubernetes configuration.

        Args:
            value: Kubernetes configuration dictionary

        Raises:
            ValueError: If validation fails
        """
        # TODO: Implement Kubernetes config validation
        # - Validate namespace
        # - Validate replicas (positive integer)
        # - Validate resource requests/limits format
        # - Validate node selector format
        
        if not isinstance(value, dict):
            raise ValueError("kubernetes_config must be a dictionary")
        
        if "namespace" not in value:
            raise ValueError("kubernetes_config.namespace is required")
        
        self.validate_namespace(value["namespace"])

    def validate_spinnaker_config(self, value: Dict[str, Any]) -> None:
        """
        Validate Spinnaker pipeline configuration.

        Args:
            value: Spinnaker configuration dictionary

        Raises:
            ValueError: If validation fails
        """
        # TODO: Implement Spinnaker config validation
        # - Validate pipeline name format
        # - Validate environments list
        # - Validate deployment strategy
        
        if not isinstance(value, dict):
            raise ValueError("spinnaker_config must be a dictionary")
        
        if "environments" in value:
            envs = value["environments"]
            if not isinstance(envs, list):
                raise ValueError("spinnaker_config.environments must be a list")
            valid_envs = ["dev", "stage", "prod", "sandbox"]
            for env in envs:
                if env not in valid_envs:
                    raise ValueError(f"Invalid environment: {env}. Must be one of: {', '.join(valid_envs)}")

    def validate_kafka_config(self, value: Dict[str, Any]) -> None:
        """
        Validate Kafka configuration.

        Args:
            value: Kafka configuration dictionary

        Raises:
            ValueError: If validation fails
        """
        # TODO: Implement Kafka config validation
        # - Validate topic names format
        # - Validate consumer group name
        # - Validate partition count
        # - Validate replication factor
        
        if not isinstance(value, dict):
            raise ValueError("kafka_config must be a dictionary")

    def validate_edge_config(self, value: Dict[str, Any]) -> None:
        """
        Validate Edge gateway configuration.

        Args:
            value: Edge configuration dictionary

        Raises:
            ValueError: If validation fails
        """
        # TODO: Implement Edge config validation
        # - Validate route configurations
        # - Validate rate limit settings
        # - Validate auth type
        
        if not isinstance(value, dict):
            raise ValueError("edge_config must be a dictionary")

    def validate_authz_config(self, value: Dict[str, Any]) -> None:
        """
        Validate Authorization configuration.

        Args:
            value: Authz configuration dictionary

        Raises:
            ValueError: If validation fails
        """
        # TODO: Implement Authz config validation
        # - Validate roles format
        # - Validate permissions format
        # - Validate policy definitions
        
        if not isinstance(value, dict):
            raise ValueError("authz_config must be a dictionary")

    def validate_monitoring_config(self, value: Dict[str, Any]) -> None:
        """
        Validate Monitoring configuration.

        Args:
            value: Monitoring configuration dictionary

        Raises:
            ValueError: If validation fails
        """
        # TODO: Implement Monitoring config validation
        # - Validate dashboard settings
        # - Validate alerting rules
        # - Validate SLO targets
        
        if not isinstance(value, dict):
            raise ValueError("monitoring_config must be a dictionary")

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate all parameters for foundation onboarding.

        This is the main entry point for parameter validation.

        Args:
            parameters: Dictionary of all parameters

        Returns:
            Validated parameters dictionary

        Raises:
            ValueError: If validation fails
        """
        # TODO: Implement full parameter validation
        # - Check required parameters are present
        # - Validate each parameter type
        # - Perform cross-field validation
        # - Return validated parameters
        
        if not isinstance(parameters, dict):
            raise ValueError("Parameters must be a dictionary")

        return self.validate_full_onboarding_parameters(parameters)

    def validate_full_onboarding_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform complete validation of all onboarding parameters.

        Args:
            parameters: Dictionary of all parameters

        Returns:
            Validated parameters dictionary

        Raises:
            ValueError: If validation fails
        """
        # TODO: Implement comprehensive parameter validation
        # - Define required parameters set
        # - Check for missing required parameters
        # - Validate each parameter using specific validators
        # - Handle optional parameters
        # - Perform cross-field validation
        # - Validate using Pydantic model
        
        required_params = {
            "service_name",
            "team_name",
            "kubernetes_config",
        }

        missing = [key for key in required_params if key not in parameters]
        if missing:
            raise ValueError(f"Missing required parameter(s): {', '.join(sorted(missing))}")

        # Validate required parameters
        self.validate_service_name(parameters["service_name"])
        self.validate_team_name(parameters["team_name"])
        self.validate_kubernetes_config(parameters["kubernetes_config"])

        # Validate optional parameters if provided
        if parameters.get("database_config"):
            self.validate_database_config(parameters["database_config"])
        
        if parameters.get("spinnaker_config"):
            self.validate_spinnaker_config(parameters["spinnaker_config"])
        
        if parameters.get("kafka_config"):
            self.validate_kafka_config(parameters["kafka_config"])
        
        if parameters.get("edge_config"):
            self.validate_edge_config(parameters["edge_config"])
        
        if parameters.get("authz_config"):
            self.validate_authz_config(parameters["authz_config"])
        
        if parameters.get("monitoring_config"):
            self.validate_monitoring_config(parameters["monitoring_config"])

        # Final validation with Pydantic model
        FoundationOnboardingRequest(**parameters)
        
        return parameters


# Global instance for validation
validator = FoundationOnboardingValidator()


# Module-level validation functions for validator discovery system
def validate_service_name(value: Any) -> Any:
    """Validate service name parameter."""
    validator.validate_service_name(value)
    return value


def validate_team_name(value: Any) -> Any:
    """Validate team name parameter."""
    validator.validate_team_name(value)
    return value


def validate_namespace(value: Any) -> Any:
    """Validate namespace parameter."""
    validator.validate_namespace(value)
    return value

