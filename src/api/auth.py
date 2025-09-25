from fastapi import Depends, status, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config.config import config

security = HTTPBearer(auto_error=False)


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify API token if authentication is enabled.

    Args:
        credentials: Bearer token credentials

    Returns:
        True if authenticated or no auth required

    Raises:
        HTTPException: If authentication fails
    """

    # If no API token is configured, allow all requests
    if not config.api_token:
        return True

    # If token is configured but no credentials provided
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token."
        )

    # Verify token
    if credentials.credentials != config.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token."
        )

    return True
