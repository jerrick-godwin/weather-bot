from unittest.mock import patch, MagicMock

import pytest
from agents import RunContextWrapper

from agent.guardrail_agent import GuardrailAgent
from src.models.guardrail.guardrail_output import GuardrailOutput


class TestGuardrailAgent:
    """Test cases for the GuardrailAgent class."""

    @pytest.mark.asyncio
    async def test_guardrail_agent_run_without_context(self, mock_config, mock_runner_run):
        """Test running guardrail agent without context."""
        GuardrailAgent._instances = {}
        agent = GuardrailAgent()

        result = await agent.run("What's the weather like?")

        mock_runner_run.assert_called_once()
        assert result is not None
        assert hasattr(result, 'final_output')

    @pytest.mark.asyncio
    async def test_guardrail_agent_run_with_context(self, mock_config, mock_runner_run):
        """Test running guardrail agent with context."""
        GuardrailAgent._instances = {}
        agent = GuardrailAgent()

        ctx = MagicMock(spec=RunContextWrapper)
        ctx.context = MagicMock()

        result = await agent.run("What's the weather like?", ctx)

        mock_runner_run.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_guardrail_agent_weather_related_query(self, mock_config):
        """Test guardrail agent correctly identifies weather-related queries."""
        GuardrailAgent._instances = {}

        with patch('agents.Runner.run') as mock_runner:
            mock_result = MagicMock()
            mock_result.final_output = GuardrailOutput(
                is_weather_related=True,
                reasoning="The query asks about weather conditions."
            )
            mock_runner.return_value = mock_result

            agent = GuardrailAgent()
            result = await agent.run("What's the weather in London?")

            assert result.final_output.is_weather_related is True
            assert "weather conditions" in result.final_output.reasoning

    @pytest.mark.asyncio
    async def test_guardrail_agent_non_weather_related_query(self, mock_config):
        """Test guardrail agent correctly identifies non-weather-related queries."""
        GuardrailAgent._instances = {}

        with patch('agents.Runner.run') as mock_runner:
            mock_result = MagicMock()
            mock_result.final_output = GuardrailOutput(
                is_weather_related=False,
                reasoning="The query is about sports, not weather."
            )
            mock_runner.return_value = mock_result

            agent = GuardrailAgent()
            result = await agent.run("What's the score of the football match?")

            assert result.final_output.is_weather_related is False
            assert "sports" in result.final_output.reasoning
