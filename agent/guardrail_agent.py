import structlog
from agents import (
    Agent,
    RunContextWrapper,
    Runner,
    TResponseInputItem
)
from openai import AsyncOpenAI

from src.config import config
from src.models.guardrail.guardrail_output import GuardrailOutput
from src.utils.singleton import Singleton

logger = structlog.get_logger(__name__)


class GuardrailAgent(Singleton):
    def __init__(self):
        """Initialize the orchestrator agent service."""
        super().__init__()

        if hasattr(self, "_guardrail_agent_initialized"):
            return

        # Configure default OpenAI client for the agents SDK
        self._openai_client = AsyncOpenAI(api_key=config.openai_api_key)

        # Define the guardrail agent
        self.agent = Agent(
            name="Weather Assistant",
            instructions="Check if the text is weather related.",
            output_type=GuardrailOutput
        )

        self._agent_initialized = True
        logger.info("Guardrail Agent has been initialized")

    async def run(
            self,
            prompt: str | list[TResponseInputItem],
            ctx: RunContextWrapper[None] | None = None
    ):
        """Execute the guardrail agent and return its result.

        Args:
            prompt: Text or structured input to analyze.
            ctx: Optional run context wrapper propagated through the agents SDK.

        Returns:
            Agents SDK result object containing `final_output` of type `GuardrailOutput`.
        """
        if ctx is None:
            result = await Runner.run(
                starting_agent=self.agent,
                input=prompt
            )
        else:
            result = await Runner.run(
                starting_agent=self.agent,
                input=prompt,
                context=ctx.context
            )

        return result


guardrail_agent = GuardrailAgent()
