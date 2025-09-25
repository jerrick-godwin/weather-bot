import structlog
from fastapi import APIRouter, Depends, status, HTTPException

from agent.guardrail_agent import guardrail_agent
from src.api.auth import verify_token
from src.models.guardrail.guardrail_output import GuardrailOutput
from src.models.guardrail.guardrail_request import GuardrailRequest
from src.models.guardrail.guardrail_response import GuardrailResponse

logger = structlog.get_logger(__name__)


# Create router
router = APIRouter(prefix="/guardrail", tags=["Guardrail"])


@router.post("/check", summary="Check if text is weather-related")
async def check_guardrail(
    request: GuardrailRequest,
    authenticated: bool = Depends(verify_token)
) -> GuardrailOutput:
    """
    Check if the provided text is weather-related using the guardrail agent.

    This endpoint analyzes the input text and determines if it pertains to weather
    or weather-related topics.

    Args:
        request: Request containing the text to analyze

    Returns:
        GuardrailOutput: Analysis result with weather relation status and reasoning

    Raises:
        HTTPException: 500 when guardrail evaluation fails.
    """
    logger.info(
        "API request: Check guardrail",
        text_length=len(request.text),
        authenticated=authenticated
    )

    try:
        result = await guardrail_agent.run(request.text)

        # Check whether the prompt is weather related
        is_weather_related = result.final_output.is_weather_related

        # Check for reasoning
        reasoning = result.final_output.reasoning

        logger.info(
            "Successfully checked guardrail",
            is_weather_related=is_weather_related,
            reasoning=reasoning
        )

        return GuardrailResponse(
            is_weather_related=is_weather_related,
            reasoning=reasoning
        )

    except Exception as e:
        logger.error(
            "Failed to check guardrail",
            error=str(e),
            text_preview=request.text[:100] + "..." if len(request.text) > 100 else request.text
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check guardrail: {str(e)}"
        )
