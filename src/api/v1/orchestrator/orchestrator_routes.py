import structlog
from fastapi import APIRouter, Depends, status, HTTPException

from src.api.auth import verify_token
from src.exceptions.orchestration import OrchestratorAgentError
from src.models.orchestrator import OrchestratorQueryRequest
from agent.weather_agent import weather_agent

logger = structlog.get_logger(__name__)


# Create router
router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])


@router.post("/query", summary="Query Weather Orchestrator")
async def query_orchestrator(
    request: OrchestratorQueryRequest,
        authenticated: bool = Depends(verify_token)
):
    """Run a query through the Weather Orchestrator agent and return the result.

    The orchestrator agent analyzes the natural-language query, invokes the
    appropriate tools (e.g., fetching current or historical weather), and
    returns a structured response.

    Args:
        request: The request payload containing the user's query string.

    Returns:
        A structured agent response suitable for API clients.

    Raises:
        HTTPException: 500 if the orchestrator fails to process the query.
    """
    try:
        logger.info(
            "Processing request query",
            query=request.query
        )
        result = await weather_agent.process_query(request.query)
        return result

    except OrchestratorAgentError as e:
        logger.error(
            "Orchestrator query failed",
            query=request.query,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )
