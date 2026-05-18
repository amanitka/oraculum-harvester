import asyncio
from types import SimpleNamespace
from typing import Any, Coroutine, TypeVar

import pytest
from pydantic import BaseModel

from common.config import config
from common.llm.litellm_client import LiteLlmClient, StructuredOutputError

T = TypeVar("T")


class StructuredResponse(BaseModel):
    """Schema used to validate structured responses in LiteLLM client tests."""

    template: str


def _build_response(
    content: str,
    *,
    finish_reason: str = "stop",
    model: str = "test-model",
    prompt_tokens: int = 7,
    completion_tokens: int = 13,
) -> SimpleNamespace:
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return SimpleNamespace(choices=[choice], usage=usage, model=model)


def _run(coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def test_complete_uses_requested_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_kwargs: dict[str, object] = {}

    async def fake_acompletion(**kwargs: object) -> SimpleNamespace:
        captured_kwargs.update(kwargs)
        return _build_response('{"template":"general"}')

    monkeypatch.setattr("common.llm.litellm_client.litellm.acompletion", fake_acompletion)

    client = LiteLlmClient(max_retries=1, initial_backoff_s=0.0)
    _run(
        client.complete(
            messages=[{"role": "user", "content": "hello"}],
            model="gemini-2.5-flash-lite",
            max_tokens=64,
            temperature=0.0,
        )
    )

    assert captured_kwargs["model"] == f"{config.llm.provider}/gemini-2.5-flash-lite"


def test_complete_retries_when_structured_response_is_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = {"count": 0}

    async def fake_acompletion(**_: object) -> SimpleNamespace:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return _build_response('{"template":"general"', finish_reason="length")
        return _build_response('{"template":"general"}', finish_reason="stop")

    monkeypatch.setattr("common.llm.litellm_client.litellm.acompletion", fake_acompletion)

    client = LiteLlmClient(max_retries=2, initial_backoff_s=0.0)
    response = _run(
        client.complete(
            messages=[{"role": "user", "content": "hello"}],
            model="gemini-2.5-flash-lite",
            max_tokens=64,
            temperature=0.0,
            response_format=StructuredResponse,
        )
    )

    assert attempts["count"] == 2
    assert response.text == '{"template":"general"}'
    assert response.finish_reason == "stop"


def test_complete_raises_when_structured_retries_are_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_acompletion(**_: object) -> SimpleNamespace:
        return _build_response('{"template":"general"', finish_reason="length")

    monkeypatch.setattr("common.llm.litellm_client.litellm.acompletion", fake_acompletion)

    client = LiteLlmClient(max_retries=2, initial_backoff_s=0.0)
    with pytest.raises(StructuredOutputError):
        _run(
            client.complete(
                messages=[{"role": "user", "content": "hello"}],
                model="gemini-2.5-flash-lite",
                max_tokens=64,
                temperature=0.0,
                response_format=StructuredResponse,
            )
        )
