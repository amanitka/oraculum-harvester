import asyncio
import logging
import time
from typing import Any, Mapping

from openai import APIConnectionError as OpenAIApiConnectionError
from openai import AsyncOpenAI
from openai import InternalServerError
from openai import RateLimitError as OpenAIRateLimitError
from pydantic import BaseModel, ValidationError

from common.config import config
from common.llm.base import LlmClient, LlmResponse

logger = logging.getLogger(__name__)
_INCOMPLETE_ERROR_TEXT = "incomplete structured response"
_MAX_RETRY_TOKENS = config.llm.router_settings.max_tokens


class StructuredOutputError(ValueError):
    """Raised when structured model output cannot be parsed reliably."""


class OpenAiClient(LlmClient):
    """
    An adapter for the official OpenAI SDK that implements the LlmClient interface and tier-based routing.
    """

    def __init__(self, max_retries: int = 3, initial_backoff_s: float = 1.0):
        self._max_retries = max_retries
        self._initial_backoff_s = initial_backoff_s

    async def complete(
        self,
        messages: list[Mapping[str, Any]],
        *,
        model: str,  # This will now be the alias, e.g., "flash-tier"
        max_tokens: int,
        temperature: float,
        response_format: type[BaseModel] | dict[str, Any] | None = None,
    ) -> LlmResponse:
        """
        Generates a completion using the OpenAI SDK with tier-based routing and retry logic.
        """
        deployments = sorted(
            [d for d in config.llm.deployments if d.alias == model],
            key=lambda d: d.order,
        )

        if not deployments:
            raise ValueError(f"No deployments found for alias '{model}'")

        last_exception = None
        for deployment in deployments:
            client = AsyncOpenAI(api_key=deployment.api_key, base_url=deployment.api_base)
            try:
                return await self._try_complete_with_deployment(
                    client,
                    messages,
                    model=deployment.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format=response_format,
                )
            except Exception as e:
                logger.warning(
                    "Deployment %s for tier %s failed. Trying next. Error: %s",
                    deployment.model,
                    model,
                    e,
                )
                last_exception = e
                continue

        raise RuntimeError(f"All deployments for tier {model} failed.") from last_exception

    async def _try_complete_with_deployment(
        self,
        client: AsyncOpenAI,
        messages: list[Mapping[str, Any]],
        *,
        model: str,
        max_tokens: int,
        temperature: float,
        response_format: type[BaseModel] | dict[str, Any] | None = None,
    ) -> LlmResponse:
        attempt = 0
        backoff = self._initial_backoff_s
        current_max_tokens = min(max_tokens, _MAX_RETRY_TOKENS)

        if current_max_tokens < max_tokens:
            logger.warning(
                "Requested max_tokens %d exceeds guardrail %d; capping request.",
                max_tokens,
                _MAX_RETRY_TOKENS,
            )

        while attempt < self._max_retries:
            try:
                start_time = time.monotonic()

                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,  # type: ignore
                    "max_tokens": current_max_tokens,
                    "temperature": temperature,
                }

                if response_format:
                    kwargs["response_format"] = {"type": "json_object"}

                response = await client.chat.completions.create(**kwargs)

                end_time = time.monotonic()

                choice = response.choices[0]
                completion_text = choice.message.content or ""
                finish_reason = getattr(choice, "finish_reason", None)

                if isinstance(response_format, type) and issubclass(response_format, BaseModel):
                    try:
                        response_format.model_validate_json(completion_text)
                    except ValidationError as exc:
                        if finish_reason in ("length", "max_tokens"):
                            raise StructuredOutputError(
                                f"incomplete structured response (finish_reason={finish_reason})"
                            ) from exc
                        raise StructuredOutputError("structured response failed validation") from exc

                usage = response.usage
                prompt_tokens = usage.prompt_tokens if usage else 0
                completion_tokens = usage.completion_tokens if usage else 0

                return LlmResponse(
                    text=completion_text,
                    model=response.model,
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                    latency_ms=int((end_time - start_time) * 1000),
                    finish_reason=finish_reason,
                )

            except (
                OpenAIRateLimitError,
                InternalServerError,
                OpenAIApiConnectionError,
            ) as e:
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

                if _INCOMPLETE_ERROR_TEXT in str(e).lower() and current_max_tokens < _MAX_RETRY_TOKENS:
                    next_max_tokens = min(
                        max(current_max_tokens * 2, current_max_tokens + 1),
                        _MAX_RETRY_TOKENS,
                    )
                    logger.warning(
                        "Increasing max_tokens for retry from %d to %d after truncation.",
                        current_max_tokens,
                        next_max_tokens,
                    )
                    current_max_tokens = next_max_tokens

                await asyncio.sleep(backoff)
                backoff *= 2

            except Exception:
                logger.exception("An unexpected error occurred during the LLM call.")
                raise

        raise RuntimeError("LLM call failed after all retries.")