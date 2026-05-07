"""
Service context manager for GenSpec.

Manages fetching and caching of Razorpay service documentation
to provide context during specification generation.
"""

import os
import json
import requests
from typing import Dict, Any, List, Optional
from pathlib import Path

from src.providers.logger import Logger
from src.api.dependencies import get_logger

logger = get_logger("service-context-manager")


class ServiceContextManager:
    """
    Manages service context for specification generation.
    
    Fetches and caches README files from Razorpay service repositories
    to provide context about existing services.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the service context manager.
        
        Args:
            config: Configuration dictionary with service context settings
        """
        self.config = config
        self.cache_dir = Path(config.get("paths", {}).get("service_context_cache", 
                                                          "src/services/agents_catalogue/genspec/cache/service_context"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load service configuration
        self.services = config.get("service_context", {}).get("services", [])
        self.enabled = config.get("service_context", {}).get("enabled", True)
        
        # Get GitHub token from config (with environment variable fallback)
        github_config = config.get("github", {})
        self.github_token = (
            github_config.get("token") or 
            os.environ.get("GITHUB_TOKEN") or 
            os.environ.get("GH_TOKEN")
        )
        
        if self.github_token:
            logger.info("GitHub token configured for service context fetching")
        else:
            logger.warning("No GitHub token found - private repository access will be limited")
        
        # Cache for loaded contexts
        self._context_cache = {}
        
        logger.info(f"Initialized ServiceContextManager with {len(self.services)} services")
    
    def get_all_service_contexts(self) -> str:
        """
        Get combined context from all configured services.
        
        Returns:
            Combined service context as a formatted string
        """
        if not self.enabled:
            logger.info("Service context is disabled")
            return ""
        
        contexts = []
        for service_config in self.services:
            context = self.get_service_context(service_config)
            if context:
                contexts.append(context)
        
        if not contexts:
            return ""
        
        # Combine all contexts with clear separation
        combined_context = "\n\n" + "="*80 + "\n"
        combined_context += "RAZORPAY SERVICE CONTEXT\n"
        combined_context += "="*80 + "\n\n"
        combined_context += "The following Razorpay services are available and should be considered when designing approaches:\n\n"
        combined_context += "\n\n".join(contexts)
        combined_context += "\n\n" + "="*80 + "\n"
        
        return combined_context
    
    def get_service_context(self, service_config: Dict[str, Any]) -> Optional[str]:
        """
        Get context for a specific service.
        
        Args:
            service_config: Service configuration with name and repo_url
            
        Returns:
            Service context string or None if unavailable
        """
        service_name = service_config.get("name")
        repo_url = service_config.get("repo_url")
        
        if not service_name or not repo_url:
            logger.warning(f"Invalid service config: {service_config}")
            return None
        
        # Check cache first
        if service_name in self._context_cache:
            logger.debug(f"Using cached context for {service_name}")
            return self._context_cache[service_name]
        
        # Try to load from disk cache
        cached_file = self.cache_dir / f"{service_name}.md"
        if cached_file.exists():
            logger.info(f"Loading cached context for {service_name} from {cached_file}")
            try:
                context = cached_file.read_text(encoding='utf-8')
                self._context_cache[service_name] = context
                return context
            except Exception as e:
                logger.warning(f"Failed to read cached context for {service_name}: {e}")
        
        # Fetch from GitHub
        context = self._fetch_readme_from_github(service_name, repo_url)
        
        if context:
            # Cache to disk
            try:
                cached_file.write_text(context, encoding='utf-8')
                logger.info(f"Cached context for {service_name} to {cached_file}")
            except Exception as e:
                logger.warning(f"Failed to cache context for {service_name}: {e}")
            
            self._context_cache[service_name] = context
            return context
        
        return None
    
    def _fetch_readme_from_github(self, service_name: str, repo_url: str) -> Optional[str]:
        """
        Fetch README from a GitHub repository.
        
        Args:
            service_name: Name of the service
            repo_url: GitHub repository URL
            
        Returns:
            README content or None if fetch fails
        """
        try:
            # Parse the GitHub URL to extract owner and repo
            # Expected format: https://github.com/razorpay/merchant_invoice/
            parts = repo_url.rstrip('/').split('/')
            if len(parts) < 2:
                logger.error(f"Invalid GitHub URL format: {repo_url}")
                return None
            
            owner = parts[-2]
            repo = parts[-1]
            
            # Try to fetch README using GitHub API
            api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
            
            logger.info(f"Fetching README for {service_name} from {api_url}")
            
            headers = {
                "Accept": "application/vnd.github.v3.raw"
            }
            
            # Add GitHub token if available
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
                logger.debug(f"Using GitHub token for API request")
            
            response = requests.get(api_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                readme_content = response.text
                
                # Format the context
                formatted_context = f"""
## Service: {service_name}

**Repository:** {repo_url}

### Service Documentation

{readme_content}
"""
                logger.info(f"Successfully fetched README for {service_name} ({len(readme_content)} characters)")
                return formatted_context
            
            elif response.status_code == 404:
                logger.warning(f"README not found via API for {service_name}, trying raw URLs")
                # Try alternative README filenames with both master and main branches
                for branch in ["main", "master"]:
                    for readme_name in ["README.md", "readme.md", "Readme.md", "README.MD"]:
                        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{readme_name}"
                        logger.debug(f"Trying URL: {raw_url}")
                        
                        try:
                            # Add headers for authentication if token is available
                            raw_headers = {}
                            if self.github_token:
                                raw_headers["Authorization"] = f"token {self.github_token}"
                            
                            response = requests.get(raw_url, headers=raw_headers, timeout=30)
                            if response.status_code == 200:
                                readme_content = response.text
                                formatted_context = f"""
## Service: {service_name}

**Repository:** {repo_url}

### Service Documentation

{readme_content}
"""
                                logger.info(f"Successfully fetched README for {service_name} from {raw_url}")
                                return formatted_context
                        except Exception as e:
                            logger.debug(f"Failed to fetch from {raw_url}: {e}")
                            continue
                
                logger.error(f"Could not find README for {service_name} in any branch (main/master)")
                return None
            
            else:
                logger.error(f"GitHub API error for {service_name}: {response.status_code} - {response.text}")
                return None
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching README for {service_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching README for {service_name}: {e}")
            return None
    
    def clear_cache(self, service_name: Optional[str] = None):
        """
        Clear cached service contexts.
        
        Args:
            service_name: Specific service to clear, or None to clear all
        """
        if service_name:
            # Clear specific service from memory cache
            if service_name in self._context_cache:
                del self._context_cache[service_name]
                logger.info(f"Cleared memory cache for {service_name}")
            
            # Clear from disk cache
            cached_file = self.cache_dir / f"{service_name}.md"
            if cached_file.exists():
                cached_file.unlink()
                logger.info(f"Cleared disk cache for {service_name}")
        else:
            # Clear all caches
            self._context_cache.clear()
            for cached_file in self.cache_dir.glob("*.md"):
                cached_file.unlink()
            logger.info("Cleared all service context caches")
    
    def add_service(self, service_name: str, repo_url: str):
        """
        Dynamically add a service to the context manager.
        
        Args:
            service_name: Name of the service
            repo_url: GitHub repository URL
        """
        service_config = {
            "name": service_name,
            "repo_url": repo_url
        }
        
        if service_config not in self.services:
            self.services.append(service_config)
            logger.info(f"Added service {service_name} to context manager")
    
    def get_contexts_for_services(self, service_names: List[str]) -> str:
        """
        Get combined context for a specific list of service names.
        Dynamically fetches from Razorpay GitHub if service is not in config.
        
        Args:
            service_names: List of service names (e.g., ["merchant_invoice", "api"])
            
        Returns:
            Combined service context string
        """
        if not service_names:
            return ""
        
        contexts = []
        for service_name in service_names:
            # Construct GitHub URL for Razorpay service
            repo_url = f"https://github.com/razorpay/{service_name}/"
            
            service_config = {
                "name": service_name,
                "repo_url": repo_url
            }
            
            logger.info(f"Fetching context for service: {service_name}")
            context = self.get_service_context(service_config)
            
            if context:
                contexts.append(context)
            else:
                logger.warning(f"Could not fetch context for service: {service_name}")
                # Add a placeholder to indicate the service was requested but not available
                contexts.append(f"""
## Service: {service_name}

**Repository:** {repo_url}

### Service Documentation

*Note: Documentation for {service_name} could not be fetched. This service may be private or the README may not be available.*
""")
        
        if not contexts:
            return ""
        
        # Combine all contexts with clear separation
        combined_context = "\n\n" + "="*80 + "\n"
        combined_context += "RAZORPAY SERVICE CONTEXT\n"
        combined_context += "="*80 + "\n\n"
        combined_context += "The following Razorpay services are available and should be considered when designing approaches:\n\n"
        combined_context += "\n\n".join(contexts)
        combined_context += "\n\n" + "="*80 + "\n"
        
        logger.info(f"Generated combined context for {len(service_names)} services ({len(combined_context)} characters)")
        return combined_context
    
    def get_service_summary(self) -> Dict[str, Any]:
        """
        Get a summary of available service contexts.
        
        Returns:
            Dictionary with service context status
        """
        summary = {
            "enabled": self.enabled,
            "total_services": len(self.services),
            "services": []
        }
        
        for service_config in self.services:
            service_name = service_config.get("name")
            cached_file = self.cache_dir / f"{service_name}.md"
            
            summary["services"].append({
                "name": service_name,
                "repo_url": service_config.get("repo_url"),
                "cached": cached_file.exists(),
                "in_memory": service_name in self._context_cache
            })
        
        return summary

