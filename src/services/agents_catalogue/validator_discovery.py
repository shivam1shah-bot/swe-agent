"""
Validator Discovery Module for Agents Catalogue

This module provides automatic discovery of parameter validators from service modules.
Validators are functions that validate specific parameters for agents catalogue services.
"""

import importlib
import logging
from typing import Dict, Any, Callable, Optional, List, Set
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger(__name__)

@dataclass
class ValidatorInfo:
    """Information about a parameter validator."""
    name: str
    function: Callable
    description: str
    module_path: str
    service_name: str

class ValidatorDiscovery:
    """
    Automatic discovery of parameter validators from agents catalogue services.
    
    This class scans service modules and finds validation functions that follow
    the naming convention: validate_<parameter_name>
    """
    
    def __init__(self):
        """Initialize the validator discovery system."""
        self.validators: Dict[str, Dict[str, ValidatorInfo]] = {}
        self._service_modules = {
            "spinnaker-v3-pipeline-generator": "src.services.agents_catalogue.spinnaker_pipeline",
            "gateway-integrations-common": "src.services.agents_catalogue.gateway_integration.gateway_integrations_common",
            # Register api-doc-generator validators module
            "api-doc-generator": "src.services.agents_catalogue.api_doc_generator.validator",
            # Register bank-uat-agent validators module
            "bank-uat-agent": "src.services.agents_catalogue.bank_uat_agent.validator",
        }
        self._discovered = False
        self.logger = logger
    
    def discover_validators(self, force_refresh: bool = False) -> None:
        """
        Discover all validators from registered service modules.
        
        Args:
            force_refresh: If True, re-discover even if already discovered
        """
        if self._discovered and not force_refresh:
            return
            
        self.logger.info("Starting validator discovery for agents catalogue services")
        
        for service_name, module_path in self._service_modules.items():
            try:
                self._discover_service_validators(service_name, module_path)
            except Exception as e:
                self.logger.warning(f"Failed to discover validators for {service_name}: {e}")
        
        self._discovered = True
        self.logger.info(f"Validator discovery completed. Found {self.get_total_validator_count()} validators")
    
    def _discover_service_validators(self, service_name: str, module_path: str) -> None:
        """
        Discover validators from a specific service module.
        
        Args:
            service_name: Name of the service
            module_path: Python module path to the service
        """
        try:
            # Import the service module
            module = importlib.import_module(module_path)
            
            # Find all functions that start with 'validate_'
            validators = {}
            
            for attr_name in dir(module):
                if attr_name.startswith('validate_') and callable(getattr(module, attr_name)):
                    validator_func = getattr(module, attr_name)
                    parameter_name = attr_name[9:]  # Remove 'validate_' prefix
                    
                    # Get function description from docstring
                    description = validator_func.__doc__ or f"Validates {parameter_name} parameter"
                    description = description.strip().split('\n')[0]  # First line only
                    
                    validator_info = ValidatorInfo(
                        name=parameter_name,
                        function=validator_func,
                        description=description,
                        module_path=module_path,
                        service_name=service_name
                    )
                    
                    validators[parameter_name] = validator_info
                    
                    self.logger.debug(f"Discovered validator: {service_name}.{parameter_name}")
            
            if validators:
                self.validators[service_name] = validators
                self.logger.info(f"Discovered {len(validators)} validators for {service_name}")
            else:
                self.logger.debug(f"No validators found for {service_name}")
                
        except ImportError as e:
            self.logger.warning(f"Could not import module {module_path}: {e}")
        except Exception as e:
            self.logger.error(f"Error discovering validators in {module_path}: {e}")
    
    def get_validator(self, service_name: str, parameter_name: str) -> Optional[ValidatorInfo]:
        """
        Get a specific validator for a service and parameter.
        
        Args:
            service_name: Name of the service
            parameter_name: Name of the parameter
            
        Returns:
            ValidatorInfo if found, None otherwise
        """
        self.discover_validators()  # Ensure discovery has run
        
        return self.validators.get(service_name, {}).get(parameter_name)
    
    def get_service_validators(self, service_name: str) -> Dict[str, ValidatorInfo]:
        """
        Get all validators for a specific service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Dictionary of parameter_name -> ValidatorInfo
        """
        self.discover_validators()  # Ensure discovery has run
        
        return self.validators.get(service_name, {})
    
    def get_all_validators(self) -> Dict[str, Dict[str, ValidatorInfo]]:
        """
        Get all discovered validators.
        
        Returns:
            Dictionary of service_name -> {parameter_name -> ValidatorInfo}
        """
        self.discover_validators()  # Ensure discovery has run
        
        return self.validators.copy()
    
    def validate_parameter(self, service_name: str, parameter_name: str, value: Any) -> Any:
        """
        Validate a parameter value using the appropriate validator.
        
        Args:
            service_name: Name of the service
            parameter_name: Name of the parameter
            value: Value to validate
            
        Returns:
            Validated (potentially transformed) value
            
        Raises:
            ValueError: If validation fails
            RuntimeError: If validator is not found
        """
        validator_info = self.get_validator(service_name, parameter_name)
        
        if not validator_info:
            raise RuntimeError(f"No validator found for {service_name}.{parameter_name}")
        
        try:
            return validator_info.function(value)
        except Exception as e:
            raise ValueError(f"Validation failed for {parameter_name}: {e}")
    
    def validate_parameters(self, service_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate multiple parameters for a service.
        
        Args:
            service_name: Name of the service
            parameters: Dictionary of parameter_name -> value
            
        Returns:
            Dictionary of validated parameters
            
        Raises:
            ValueError: If any validation fails
        """
        # Handle nested parameter structure for gateway integrations (backward compatibility)
        if service_name == "gateway-integrations-common":
            if 'parameters' in parameters and isinstance(parameters['parameters'], dict):
                nested_params = parameters['parameters']
                if any(key in nested_params for key in ["gateway_name", "method", "countries_applicable"]):
                    self.logger.debug("Detected nested parameter structure for gateway integrations, extracting inner parameters")
                    parameters = nested_params
        
        validated = {}
        service_validators = self.get_service_validators(service_name)

        # Enforce required parameters if declared by the service validators module
        required_params: Set[str] = set()
        try:
            module_path = self._service_modules.get(service_name)
            if module_path:
                module = importlib.import_module(module_path)
                # Support either REQUIRED_PARAMETERS constant or required_parameters() function
                if hasattr(module, 'REQUIRED_PARAMETERS'):
                    maybe = getattr(module, 'REQUIRED_PARAMETERS')
                    if isinstance(maybe, (list, set, tuple)):
                        required_params = set(maybe)
                if hasattr(module, 'required_parameters') and callable(getattr(module, 'required_parameters')):
                    # Function takes precedence if both exist
                    required_params = set(getattr(module, 'required_parameters')())
        except Exception as e:
            self.logger.debug(f"Could not load required parameters for {service_name}: {e}")

        # Validate presence of required parameters
        for req in required_params:
            if req not in parameters or parameters.get(req) in (None, ''):
                raise ValueError(f"Missing required parameter: {req}")
        
        for param_name, value in parameters.items():
            if param_name in service_validators:
                try:
                    validated[param_name] = self.validate_parameter(service_name, param_name, value)
                except (ValueError, RuntimeError) as e:
                    self.logger.error(f"Parameter validation failed: {e}")
                    raise
            else:
                # No validator found, pass through as-is
                validated[param_name] = value
        
        return validated
    
    def has_validator(self, service_name: str, parameter_name: str) -> bool:
        """
        Check if a validator exists for a service and parameter.
        
        Args:
            service_name: Name of the service
            parameter_name: Name of the parameter
            
        Returns:
            True if validator exists, False otherwise
        """
        return self.get_validator(service_name, parameter_name) is not None
    
    def get_validator_description(self, service_name: str, parameter_name: str) -> Optional[str]:
        """
        Get the description of a validator.
        
        Args:
            service_name: Name of the service
            parameter_name: Name of the parameter
            
        Returns:
            Validator description if found, None otherwise
        """
        validator_info = self.get_validator(service_name, parameter_name)
        return validator_info.description if validator_info else None
    
    def get_total_validator_count(self) -> int:
        """
        Get the total number of discovered validators.
        
        Returns:
            Total count of validators across all services
        """
        return sum(len(validators) for validators in self.validators.values())
    
    def get_service_names(self) -> Set[str]:
        """
        Get the names of all services with discovered validators.
        
        Returns:
            Set of service names
        """
        self.discover_validators()  # Ensure discovery has run
        return set(self.validators.keys())
    
    @lru_cache(maxsize=128)
    def get_parameter_names(self, service_name: str) -> Set[str]:
        """
        Get the names of all parameters with validators for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Set of parameter names (cached for performance)
        """
        service_validators = self.get_service_validators(service_name)
        return set(service_validators.keys())

# Global instance for use throughout the application
validator_discovery = ValidatorDiscovery() 