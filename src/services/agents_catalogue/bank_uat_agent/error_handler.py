"""
Enhanced Error Handler for Bank UAT Agent

This module provides comprehensive error handling capabilities for the bank UAT agent,
including error categorization, logging, and recovery strategies.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from src.providers.logger import Logger


class ErrorCategory(Enum):
    """Error categories for classification and handling"""
    VALIDATION = "validation"
    FILE_IO = "file_io"
    CRYPTO = "crypto"
    NETWORK = "network"
    API = "api"
    CONFIGURATION = "configuration"
    PERMISSION = "permission"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class EnhancedErrorHandler:
    """Enhanced error handler with categorization and recovery strategies"""

    def __init__(self, logger: Logger):
        """Initialize the error handler with a logger instance"""
        self.logger = logger
        self.error_counts: Dict[ErrorCategory, int] = {category: 0 for category in ErrorCategory}
        self.recovery_strategies: Dict[ErrorCategory, List[str]] = self._initialize_recovery_strategies()

    def _initialize_recovery_strategies(self) -> Dict[ErrorCategory, List[str]]:
        """Initialize recovery strategies for each error category"""
        return {
            ErrorCategory.VALIDATION: [
                "Retry with corrected parameters",
                "Validate input format and constraints",
                "Check required field presence"
            ],
            ErrorCategory.FILE_IO: [
                "Check file permissions and existence",
                "Verify file path and format",
                "Ensure sufficient disk space"
            ],
            ErrorCategory.CRYPTO: [
                "Verify key format and validity",
                "Check encryption algorithm compatibility",
                "Validate key pair matching"
            ],
            ErrorCategory.NETWORK: [
                "Retry with exponential backoff",
                "Check network connectivity",
                "Verify endpoint availability"
            ],
            ErrorCategory.API: [
                "Retry with appropriate delays",
                "Check API rate limits",
                "Verify authentication credentials"
            ],
            ErrorCategory.CONFIGURATION: [
                "Validate configuration parameters",
                "Check environment variables",
                "Verify service dependencies"
            ],
            ErrorCategory.PERMISSION: [
                "Check user permissions",
                "Verify authentication status",
                "Request elevated access if needed"
            ],
            ErrorCategory.TIMEOUT: [
                "Increase timeout values",
                "Optimize request payloads",
                "Check system resources"
            ],
            ErrorCategory.UNKNOWN: [
                "Log detailed error information",
                "Check system logs",
                "Contact support with error details"
            ]
        }

    def handle_error(self, error: Exception, category: ErrorCategory, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Handle an error with categorization and logging
        
        Args:
            error: The exception that occurred
            category: Error category for classification
            context: Additional context information
            
        Returns:
            Dictionary containing error details and recovery suggestions
        """
        # Increment error count for the category
        self.error_counts[category] += 1
        
        # Prepare error context
        error_context = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "error_category": category.value,
            "error_count": self.error_counts[category],
            "context": context or {},
            "recovery_suggestions": self.recovery_strategies[category]
        }
        
        # Log the error with appropriate level
        if category in [ErrorCategory.VALIDATION, ErrorCategory.CONFIGURATION]:
            self.logger.warning(f"{category.value.upper()} Error: {str(error)}", extra=error_context)
        elif category in [ErrorCategory.PERMISSION, ErrorCategory.CRYPTO]:
            self.logger.error(f"{category.value.upper()} Error: {str(error)}", extra=error_context)
        else:
            self.logger.error(f"{category.value.upper()} Error: {str(error)}", extra=error_context)
        
        return error_context

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all errors encountered"""
        total_errors = sum(self.error_counts.values())
        return {
            "total_errors": total_errors,
            "errors_by_category": {category.value: count for category, count in self.error_counts.items()},
            "most_common_error": max(self.error_counts.items(), key=lambda x: x[1])[0].value if total_errors > 0 else None
        }

    def reset_error_counts(self):
        """Reset all error counts to zero"""
        self.error_counts = {category: 0 for category in ErrorCategory}
        self.logger.info("Error counts reset to zero")

    def suggest_recovery(self, category: ErrorCategory) -> List[str]:
        """Get recovery suggestions for a specific error category"""
        return self.recovery_strategies.get(category, [])

    def log_recovery_attempt(self, category: ErrorCategory, strategy: str, success: bool):
        """Log a recovery attempt"""
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(f"Recovery attempt {status} for {category.value}: {strategy}")

    def get_critical_errors(self) -> List[Dict[str, Any]]:
        """Get list of critical errors that require immediate attention"""
        critical_categories = [ErrorCategory.PERMISSION, ErrorCategory.CRYPTO, ErrorCategory.CONFIGURATION]
        critical_errors = []
        
        for category in critical_categories:
            if self.error_counts[category] > 0:
                critical_errors.append({
                    "category": category.value,
                    "count": self.error_counts[category],
                    "recovery_suggestions": self.recovery_strategies[category]
                })
        
        return critical_errors 