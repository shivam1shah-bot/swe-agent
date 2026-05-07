"""
Repository Configuration for Bank Integration

Defines the repositories involved in bank integration workflows.
"""

from typing import Dict


class BankRepositoryConfig:
    """Configuration for repositories involved in bank integration."""
    
    # Core integration repositories
    INTEGRATIONS_GO = "https://github.com/razorpay/integrations-go"
    FTS = "https://github.com/razorpay/fts"
    PAYOUTS = "https://github.com/razorpay/payouts"
    X_BALANCES = "https://github.com/razorpay/x-balances"
    TERMINALS = "https://github.com/razorpay/terminals"
    KUBE_MANIFESTS = "https://github.com/razorpay/kube-manifests"
    
    @classmethod
    def get_enabled_repositories(cls, enable_integrations_go: bool = True,
                                enable_fts: bool = True,
                                enable_payouts: bool = True,
                                enable_xbalance: bool = True,
                                enable_terminals: bool = True,
                                enable_kube_manifests: bool = True) -> Dict[str, str]:
        """
        Get enabled repositories based on service flags.
        
        Args:
            enable_integrations_go: Whether to include integrations-go
            enable_fts: Whether to include FTS
            enable_payouts: Whether to include Payouts
            enable_xbalance: Whether to include X-Balance
            enable_terminals: Whether to include Terminals
            enable_kube_manifests: Whether to include Kube-manifests
            
        Returns:
            Dictionary of repository name to URL mappings
        """
        repositories = {}
        
        if enable_integrations_go:
            repositories["integrations-go"] = cls.INTEGRATIONS_GO
            
        if enable_fts:
            repositories["fts"] = cls.FTS
            
        if enable_payouts:
            repositories["payouts"] = cls.PAYOUTS
            
        if enable_xbalance:
            repositories["x-balances"] = cls.X_BALANCES
            
        if enable_terminals:
            repositories["terminals"] = cls.TERMINALS
            
        if enable_kube_manifests:
            repositories["kube-manifests"] = cls.KUBE_MANIFESTS
            
        return repositories
    
    @classmethod
    def get_all_repositories(cls) -> Dict[str, str]:
        """Get all available repositories."""
        return {
            "integrations-go": cls.INTEGRATIONS_GO,
            "fts": cls.FTS,
            "payouts": cls.PAYOUTS,
            "x-balances": cls.X_BALANCES,
            "terminals": cls.TERMINALS,
            "mozart": cls.MOZART,
            "pg-router": cls.PG_ROUTER,
            "api": cls.API
        }
    
    @classmethod
    def get_repository_display_names(cls) -> Dict[str, str]:
        """Get display names for repositories."""
        return {
            "integrations-go": "Integrations Go",
            "fts": "Fund Transfer Service",
            "payouts": "Payouts Service",
            "x-balances": "X-Balance Service",
            "terminals": "Terminals Service",
            "mozart": "Mozart",
            "pg-router": "PG Router",
            "api": "API"
        }
