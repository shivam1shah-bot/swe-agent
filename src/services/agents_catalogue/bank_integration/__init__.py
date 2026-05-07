"""
Bank Integration Service for SWE Agent

This service migrates the bank integration generator from server1.py to the SWE Agent platform,
providing multi-service code generation across integrations-go, FTS, Payouts, and X-Balance.
"""

from .service import BankIntegrationService
from .bank_integration_state import BankIntegrationState
from .repository_config import BankRepositoryConfig

__all__ = [
    'BankIntegrationService',
    'BankIntegrationState', 
    'BankRepositoryConfig'
]


