from pydantic import BaseModel, Field


class ManualUpdateRequest(BaseModel):
    """Request model for manual updates."""

    type: str = Field(..., description="Type of update: 'current' or 'backfill'")
