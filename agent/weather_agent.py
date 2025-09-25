from datetime import datetime, timedelta
from typing import Any, Dict

import structlog
from agents import (
    Agent,
    Runner,
    RunContextWrapper,
    TResponseInputItem,
    GuardrailFunctionOutput,
    function_tool,
    InputGuardrail,
    OutputGuardrail
)
from agents.exceptions import InputGuardrailTripwireTriggered
from openai import AsyncOpenAI

from agent.guardrail_agent import guardrail_agent
from src.config.config import config
from src.exceptions import BigQueryServiceError
from src.exceptions.orchestration import OrchestratorAgentError
from src.models.orchestrator.agent_response import AgentResponse
from src.services.bigquery_service import bigquery_service
from src.services.weather_service import weather_service
from src.utils.singleton import Singleton

logger = structlog.get_logger(__name__)


class WeatherAgent(Singleton):
    def __init__(self):
        """Initialize the orchestrator agent service."""
        super().__init__()

        if hasattr(self, "_weather_agent_initialized"):
            return

        # Configure default OpenAI client for the agents SDK
        self._openai_client = AsyncOpenAI(api_key=config.openai_api_key)

        # Define the weather agent
        self.agent = Agent(
            name="Weather Assistant",
            instructions="""
            You are a helpful weather information assistant. 
            You provide current and historical weather data for cities worldwide.
            - Use the available tools to get accurate, up-to-date information.
            - Present information in a clear, conversational, and user-friendly manner.
            - When asked for history or summaries, analyze the data to provide insights and trends.
            - Always specify the units (e.g., Celsius for temperature).
            """,
            tools=[
                self._get_current_weather,
                self._get_weather_history,
                self._get_weather_summary
            ],
            input_guardrails=[
                InputGuardrail(guardrail_function=self._weather_input_guardrail)
            ],
            output_guardrails=[
                OutputGuardrail(guardrail_function=self._weather_output_guardrail)
            ],
            output_type=AgentResponse
        )

        self._agent_initialized = True
        logger.info("Weather Agent has been initialized")

    @staticmethod
    async def _weather_input_guardrail(
            ctx: RunContextWrapper[None],
            agent: Agent,
            input: str | list[TResponseInputItem]
    ):
        result = await guardrail_agent.run(
            prompt=input,
            ctx=ctx.context
        )

        # If the prompt is weather related, guardrail should not be triggered
        tripwire_triggered = not result.final_output.is_weather_related

        return GuardrailFunctionOutput(
            output_info=result.final_output,
            tripwire_triggered=tripwire_triggered,
        )

    @staticmethod
    async def _weather_output_guardrail(
            ctx: RunContextWrapper,
            agent: Agent,
            output: AgentResponse
    ):
        result = await guardrail_agent.run(
            prompt=output.response,
            ctx=ctx.context
        )

        # If the response is weather related, guardrail should not be triggered
        tripwire_triggered = not result.final_output.is_weather_related

        return GuardrailFunctionOutput(
            output_info=result.final_output,
            tripwire_triggered=tripwire_triggered,
        )

    @staticmethod
    @function_tool
    async def _get_current_weather(city: str) -> Dict[str, Any]:
        """
        Get the current weather for a specific city.

        This tool first checks the database for recent data and falls back to a live API call if necessary.

        Args:
            city: The name of the city to get the weather for.
        """
        try:
            # Check database first for recent data
            weather_record = await bigquery_service.get_latest_weather(city)
            if weather_record and (datetime.now() - weather_record.data_timestamp) <= timedelta(hours=2):
                return {"source": "database", **weather_record.model_dump()}

            # Fallback to live API
            live_weather = await weather_service.get_current_weather(city)
            return {"source": "live_api", **live_weather.model_dump()}

        except Exception as e:
            logger.error("Error getting current weather", city=city, error=str(e))
            return {"error": f"Could not retrieve current weather for {city}: {str(e)}"}

    @staticmethod
    @function_tool
    async def _get_weather_history(city: str, days: int = 7) -> Dict[str, Any]:
        """
        Get the historical weather data for a city over a specified number of days.

        Args:
            city: The name of the city.
            days: The number of past days to retrieve history for (default is 7).
        """
        try:
            records = await bigquery_service.get_weather_history(city, days)
            if not records:
                return {"error": f"No historical data found for {city} for the last {days} days."}

            return {"history": [record.model_dump() for record in records]}

        except BigQueryServiceError as e:
            logger.error("Error getting weather history", city=city, error=str(e))
            return {"error": f"Failed to retrieve weather history for {city}: {str(e)}"}

    @staticmethod
    @function_tool
    async def _get_weather_summary(city: str, days: int = 7) -> Dict[str, Any]:
        """
        Get a statistical summary of the weather for a city over a specified number of days.

        Args:
            city: The name of the city.
            days: The number of past days to summarize (default is 7).
        """
        try:
            summary = await bigquery_service.get_weather_summary(city, days)
            return summary

        except BigQueryServiceError as e:
            logger.error("Error getting weather summary", city=city, error=str(e))
            return {"error": f"Failed to retrieve weather summary for {city}: {str(e)}"}

    async def run(
            self,
            prompt: str | list[TResponseInputItem],
            ctx: RunContextWrapper[None] | None = None
    ):
        """Execute the weather agent and return the agents SDK result object.

        Args:
            prompt: User's natural language input or structured items.
            ctx: Optional run context for the agents SDK.

        Returns:
            Agents SDK result with `final_output` of type `AgentResponse`.
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

    async def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a natural language weather query using the agent.

        Args:
            query: The natural language query from the user.

        Returns:
            A dictionary containing the agent's response and metadata.
        """
        start_time = datetime.now()
        logger.info("Processing weather agent query", query=query, query_length=len(query))

        try:
            result = await self.run(
                prompt=query,
                ctx=None
            )
            processing_time = (datetime.now() - start_time).total_seconds()
            response_data = {
                "response": str(result.final_output.response),
                "query": query,
                "processing_time": processing_time
            }
            logger.info(
                "Agent query processed successfully",
               query=query,
               processing_time=processing_time,
               response_length=len(response_data["response"])
            )

            return response_data

        except InputGuardrailTripwireTriggered as e:
            logger.warning("Guardrail triggered for non-weather query", query=query)
            return {
                "response": "I am a weather assistant and can only answer weather-related questions. "
                            "Please ask me about the weather.",
                "query": query,
                "processing_time": (datetime.now() - start_time).total_seconds(),
                "error": "Guardrail triggered",
            }

        except Exception as e:
            logger.error("Error processing agent query", query=query, error=str(e))
            raise OrchestratorAgentError(f"Failed to process agent query: {str(e)}")


weather_agent = WeatherAgent()
