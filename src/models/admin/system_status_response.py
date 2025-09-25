from pydantic import BaseModel, Field
from typing import Dict, Any


class SystemStatusResponse(BaseModel):
    """Response model for system status."""

    status: str = Field(..., description="Overall system status")
    timestamp: str = Field(..., description="Status check timestamp")
    services: Dict[str, Any] = Field(..., description="Individual service statuses")
    database_stats: Dict[str, Any] = Field(..., description="Database statistics")
