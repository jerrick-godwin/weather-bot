from pydantic import BaseModel


class GuardrailRequest(BaseModel):
    text: str
