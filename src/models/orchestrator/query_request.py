from pydantic import BaseModel, Field


class OrchestratorQueryRequest(BaseModel):
    query: str = Field(..., description="Natural language weather query")
