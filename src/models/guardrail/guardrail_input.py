from pydantic import BaseModel


class GuardrailInput(BaseModel):
    is_weather_related: bool
    reasoning: str
