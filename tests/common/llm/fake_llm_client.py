from typing import Any, Mapping

from pydantic import BaseModel

from common.llm.base import LlmClient, LlmResponse


class FakeLlmClient(LlmClient):
    """
    A fake LLM client for testing.
    """

    def __init__(self, canned_response_text: str = "{}"):
        self.canned_response_text = canned_response_text

    async def complete(
        self,
        messages: list[Mapping[str, Any]],
        *,
        model: str,
        max_tokens: int,
        temperature: float,
        response_format: type[BaseModel] | dict[str, Any] | None = None,
    ) -> LlmResponse:
        return LlmResponse(
            text=self.canned_response_text,
            model="fake-model",
            input_tokens=10,
            output_tokens=20,
            latency_ms=50,
        )
