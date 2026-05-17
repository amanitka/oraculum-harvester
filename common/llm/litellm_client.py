import logging
import time
from typing import Any, Mapping

import litellm
from litellm.exceptions import APIConnectionError, RateLimitError, ServiceUnavailableError
from pydantic import BaseModel

from common.config import config
from common.llm.base import LlmClient, LlmResponse

logger = logging.getLogger(__name__)

# Configure LiteLLM to use the provider specified in the config
litellm.set_verbose = False


class LiteLlmClient(LlmClient):
    """
    An adapter for LiteLLM that implements the LlmClient interface.
    """

    def __init__(self, max_retries: int = 3, initial_backoff_s: float = 1.0):
        self._max_retries = max_retries
        self._initial_backoff_s = initial_backoff_s

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
        Generates a completion using LiteLLM with retry logic.
        """
        attempt = 0
        backoff = self._initial_backoff_s

        while attempt < self._max_retries:
            try:
                start_time = time.monotonic()

                # Prepare response_format for LiteLLM
                litellm_response_format = None
                if response_format:
                    if isinstance(response_format, dict):
                        litellm_response_format = response_format
                    elif issubclass(response_format, BaseModel):
                        litellm_response_format = {"type": "json_object", "schema": response_format.model_json_schema()}
                    else:
                        raise TypeError(f"Unsupported response_format type: {type(response_format)}")

                response = await litellm.acompletion(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format=litellm_response_format,
                    # Pass the provider from config if needed, though LiteLLM often infers it
                    # custom_llm_provider=config.llm.provider,
                )
                end_time = time.monotonic()

                completion_text = response.choices[0].message.content or ""
                usage = response.usage

                return LlmResponse(
                    text=completion_text,
                    model=response.model,
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                    latency_ms=int((end_time - start_time) * 1000),
                )

            except (RateLimitError, ServiceUnavailableError, APIConnectionError) as e:
                attempt += 1
                logger.warning(
                    f"LLM call failed with transient error ({type(e).__name__}). "
                    f"Retrying in {backoff:.2f}s... ({attempt}/{self._max_retries})"
                )
                if attempt >= self._max_retries:
                    logger.error("LLM call failed after multiple retries.")
                    raise
                
                import asyncio
                await asyncio.sleep(backoff)
                backoff *= 2  # Exponential backoff

            except Exception as e:
                logger.exception("An unexpected error occurred during the LLM call.")
                raise

        # This line should not be reachable due to the raise in the retry loop
        raise RuntimeError("LLM call failed after all retries.")
