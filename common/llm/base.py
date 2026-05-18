from abc import ABC, abstractmethod
from typing import Any, Mapping

from pydantic import BaseModel, Field


class LlmResponse(BaseModel):
    """
    Standardized response from the LLM adapter.
    """

    text: str = Field(description="The generated text response from the LLM.")
    model: str = Field(description="The model name that serviced the request.")
    input_tokens: int = Field(default=0, description="Number of tokens in the prompt.")
    output_tokens: int = Field(
        default=0, description="Number of tokens in the completion."
    )
    latency_ms: int = Field(
        default=0, description="Time taken to generate the response in milliseconds."
    )
    finish_reason: str | None = Field(
        default=None,
        description="Provider-specific finish reason for the completion, when available.",
    )


class LlmClient(ABC):
    """
    Abstract Base Class for an LLM provider client.
    Ensures provider-agnostic usage throughout the system.
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[Mapping[str, Any]],
        *,
        model: str,
        max_tokens: int,
        temperature: float,
        response_format: type[BaseModel] | dict[str, Any] | None = None,
    ) -> LlmResponse:
        """
        Generates a completion from an LLM.

        Args:
            messages: A list of message dictionaries (e.g., {"role": "user", "content": "..."}).
            model: The identifier of the model to use.
            max_tokens: The maximum number of tokens to generate.
            temperature: Sampling temperature (0.0 to 2.0).
            response_format: Optional. If a Pydantic model type is provided, the LLM will
                             be instructed to return a JSON object matching that schema.
                             If a dict is provided, it's passed raw to the provider (e.g., {"type": "json_object"}).

        Returns:
            An LlmResponse containing the generated text and metadata.
        """
        pass
