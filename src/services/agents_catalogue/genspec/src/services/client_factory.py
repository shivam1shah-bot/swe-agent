"""
Simple client factory - returns the appropriate client class based on provider setting.
Minimal code change solution.
"""



from typing import Dict, Any, Type

def build_genspec_config() -> Dict[str, Any]:
    from src.providers.logger import get_logger
    from src.providers.config_loader import get_aws_config, get_config
    import tomllib
    from pathlib import Path
    logger = get_logger("client-factory")
    """
    Build GenSpec configuration from global config and static config.
    
    Merges static config from config.toml with AWS config and google_api from environment.
    
    Args:
        global_config: Global configuration dictionary
        
    Returns:
        Dictionary containing GenSpec configuration
    """
    current_file = Path(__file__).resolve()
    genspec_dir = current_file.parent.parent.parent
    static_config_path = genspec_dir / "config.toml"
    
    # Reduce logging to avoid performance impact during initialization
    static_config = {}
    if static_config_path.exists():
        try:
            with open(static_config_path, "rb") as f:
                static_config = tomllib.load(f)
        except Exception as e:
            logger.error(f"Error loading static GenSpec config: {e}", exc_info=True)
    else:
        logger.warning(f"Config file not found at: {static_config_path}")
    
    # Load environment-specific overrides
    global_config = get_config()
    # Reduce logging verbosity to avoid performance impact
    google_api_config = global_config.get("google_api", {})
    
    # Get genspec config from static config
    static_genspec_config = static_config.get("genspec", {})
    
    # Merge Bedrock configuration into AWS configuration
    aws_config = get_aws_config("claude")
    bedrock_config = static_genspec_config.get("bedrock", {})
    if bedrock_config:
        aws_config.update(bedrock_config)
    
    agents_config = global_config.get("agents", {})
    claude_code_config = agents_config.get("claude_code", {})
    provider = claude_code_config.get("provider")
    gcp_config = global_config.get("gcp", {})
    google_adk_config = global_config.get("google_adk", {})
    github_config = global_config.get("github", {})
    # print(f"Google adk configuration from claude_code config: {google_adk_config}")
    result = {
        "aws": aws_config,
        "paths": static_config.get("paths", {}),
        "templates": static_config.get("templates", {}),
        "analysis": static_config.get("analysis", {}),
        "langchain": static_config.get("langchain", {}),
        "import": static_config.get("import", {}),
        "prompts": static_config.get("prompts", {}),
        "ignore_patterns": static_config.get("ignore_patterns", {}),
        "google_api": google_api_config,
        "provider": provider,
        "gcp": gcp_config,
        "google_adk": google_adk_config,
        "github": github_config,
        "service_context": static_config.get("service_context", {})
    }
    
    return result

def get_client_class(provider: str) -> Type:
    """
    Returns the appropriate client class based on provider setting.
    """
    # Use passed config if available, otherwise get from global config
    # This avoids unnecessary get_config() calls which can be slow
    if provider == "bedrock":
        from src.services.agents_catalogue.genspec.src.services.bedrock_client import BedrockClient
        if BedrockClient is None:
            raise ImportError("BedrockClient is not available. Please install required dependencies.")
        return BedrockClient
    elif provider == "vertex_ai":
        from src.services.agents_catalogue.genspec.src.services.vertex_client import VertexClient
        from src.services.agents_catalogue.genspec.src.services.bedrock_client import BedrockClient
        if VertexClient is None:
            if BedrockClient is None:
                raise ImportError("Neither VertexClient nor BedrockClient is available. Please install required dependencies.")
            return BedrockClient
        return VertexClient
    
