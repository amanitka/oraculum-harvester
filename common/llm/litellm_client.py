import asyncio
import logging
import time
from typing import Any, Mapping

import litellm
from litellm.exceptions import APIConnectionError, RateLimitError, ServiceUnavailableError
from pydantic import BaseModel, ValidationError

from common.config import config
from common.llm.base import LlmClient, LlmResponse

logger = logging.getLogger(__name__)

# Configure LiteLLM to use the provider specified in the config
litellm.set_verbose = False
_INCOMPLETE_FINISH_REASONS = {"length", "max_tokens"}


class StructuredOutputError(ValueError):
    """Raised when structured model output cannot be parsed reliably."""


class LiteLlmClient(LlmClient):
    """
    An adapter for LiteLLM that implements the LlmClient interface.
    """

    def __init__(self, max_retries: int = 3, initial_backoff_s: float = 1.0):
        self._max_retries = max_retries
        self._initial_backoff_s = initial_backoff_s

    @staticmethod
    def _resolve_model_name(model: str) -> str:
        if "/" in model:
            return model
        return f"{config.llm.provider}/{model}"

    @staticmethod
    def _resolve_schema_model(
        response_format: type[BaseModel] | dict[str, Any] | None,
    ) -> type[BaseModel] | None:
        if response_format is None or isinstance(response_format, dict):
            return None
        if isinstance(response_format, type) and issubclass(response_format, BaseModel):
            return response_format
        raise TypeError(f"Unsupported response_format type: {type(response_format)}")

    @classmethod
    def _build_response_format(
        cls,
        response_format: type[BaseModel] | dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if response_format is None:
            return None
        if isinstance(response_format, dict):
            return response_format
        cls._resolve_schema_model(response_format)
        return {"type": "json_object"}

    @classmethod
    def _validate_structured_output(
        cls,
        response_format: type[BaseModel] | dict[str, Any] | None,
        completion_text: str,
        finish_reason: str | None,
    ) -> None:
        schema_model = cls._resolve_schema_model(response_format)
        if schema_model is None:
            return

        try:
            schema_model.model_validate_json(completion_text)
        except ValidationError as exc:
            normalized_reason = (finish_reason or "").lower()
            if normalized_reason in _INCOMPLETE_FINISH_REASONS:
                raise StructuredOutputError(
                    f"incomplete structured response (finish_reason={finish_reason})"
                ) from exc
            raise StructuredOutputError("structured response failed validation") from exc

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
        litellm_response_format = self._build_response_format(response_format)
        resolved_model = self._resolve_model_name(model)

        while attempt < self._max_retries:
            try:
                start_time = time.monotonic()

                response = await litellm.acompletion(
                    model=resolved_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format=litellm_response_format,
                    api_key=config.llm.api_key,
                    base_url=config.llm.api_base,
                )
                end_time = time.monotonic()

                choice = response.choices[0]
                completion_text = choice.message.content or ""
                finish_reason = getattr(choice, "finish_reason", None)

                self._validate_structured_output(
                    response_format=response_format,
                    completion_text=completion_text,
                    finish_reason=finish_reason,
                )

                usage = response.usage
                prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)

                return LlmResponse(
                    text=completion_text,
                    model=response.model,
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                    latency_ms=int((end_time - start_time) * 1000),
                    finish_reason=finish_reason,
                )

            except (RateLimitError, ServiceUnavailableError, APIConnectionError) as e:
                attempt += 1
                logger.warning(
                    "LLM call failed with transient error (%s). Retrying in %.2fs... (%d/%d)",
                    type(e).__name__,
                    backoff,
                    attempt,
                    self._max_retries,
                )
                if attempt >= self._max_retries:
                    logger.error("LLM call failed after multiple retries.")
                    raise

                await asyncio.sleep(backoff)
                backoff *= 2

            except StructuredOutputError as e:
                attempt += 1
                logger.warning(
                    "LLM structured output invalid (%s). Retrying in %.2fs... (%d/%d)",
                    e,
                    backoff,
                    attempt,
                    self._max_retries,
                )
                if attempt >= self._max_retries:
                    logger.error("LLM structured output failed after multiple retries.")
                    raise

                await asyncio.sleep(backoff)
                backoff *= 2

            except Exception:
                logger.exception("An unexpected error occurred during the LLM call.")
                raise

        # This line should not be reachable due to the raise in the retry loop
        raise RuntimeError("LLM call failed after all retries.")
