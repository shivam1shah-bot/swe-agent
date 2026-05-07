import jwt
import time
from typing import Dict, Any, Optional
from src.providers.config_loader import get_config
from src.providers.logger import Logger

logger = Logger(__name__)

# Constants
ALGORITHM = "HS256"
# Token lifetime: 24 hours
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

def get_secret_key() -> str:
    """Get the secret key from configuration."""
    config = get_config()
    # Get jwt_secret from google_oauth section
    return config.get("google_oauth", {}).get("jwt_secret", "development_secret_key_change_in_prod")

def create_access_token(data: Dict[str, Any], expires_delta: Optional[int] = None) -> str:
    """
    Create a new JWT access token.

    Args:
        data: Payload data to include in the token
        expires_delta: Optional expiration time in minutes

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta is not None:
        expire = time.time() + (expires_delta * 60)
    else:
        expire = time.time() + (ACCESS_TOKEN_EXPIRE_MINUTES * 60)

    # JWT libraries expect numeric (int) timestamps for exp
    to_encode.update({"exp": int(expire)})

    encoded_jwt = jwt.encode(to_encode, get_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        return None

