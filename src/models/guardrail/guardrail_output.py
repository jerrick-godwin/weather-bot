from pydantic import BaseModel


class GuardrailOutput(BaseModel):
    is_weather_related: bool
    reasoning: str
