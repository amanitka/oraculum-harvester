import asyncio
from types import SimpleNamespace
from typing import Any, Coroutine, TypeVar

import pytest
from pydantic import BaseModel

from common.llm.openai_client import (
    _MAX_RETRY_TOKENS,
    OpenAiClient,
    StructuredOutputError,
)

T = TypeVar("T")


class StructuredResponse(BaseModel):
    template: str


def _build_response(
    content: str,
    *,
    finish_reason: str = "stop",
    model: str = "test-model",
    prompt_tokens: int = 5,
    completion_tokens: int = 9,
) -> SimpleNamespace:
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return SimpleNamespace(choices=[choice], usage=usage, model=model)


def _run(coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def test_complete_increases_max_tokens_for_truncated_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_async_openai(**_: object) -> SimpleNamespace:
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=None)))

    monkeypatch.setattr("common.llm.openai_client.AsyncOpenAI", fake_async_openai)

    client = OpenAiClient(max_retries=2, initial_backoff_s=0.0)
    captured_max_tokens: list[int] = []
    responses = [
        _build_response('{"template":"general"', finish_reason="length"),
        _build_response('{"template":"general"}', finish_reason="stop"),
    ]

    async def fake_create(**kwargs: object) -> SimpleNamespace:
        captured_max_tokens.append(int(kwargs["max_tokens"]))
        return responses[len(captured_max_tokens) - 1]

    client._client.chat.completions.create = fake_create  # type: ignore[attr-defined]

    response = _run(
        client.complete(
            messages=[{"role": "user", "content": "hello"}],
            model="gemini-2.5-pro",
            max_tokens=128,
            temperature=0.0,
            response_format=StructuredResponse,
        )
    )

    assert captured_max_tokens == [128, 256]
    assert response.text == '{"template":"general"}'
    assert response.finish_reason == "stop"


def test_complete_raises_after_exhausting_truncated_structured_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_async_openai(**_: object) -> SimpleNamespace:
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=None)))

    monkeypatch.setattr("common.llm.openai_client.AsyncOpenAI", fake_async_openai)

    client = OpenAiClient(max_retries=2, initial_backoff_s=0.0)
    captured_max_tokens: list[int] = []

    async def fake_create(**kwargs: object) -> SimpleNamespace:
        captured_max_tokens.append(int(kwargs["max_tokens"]))
        return _build_response('{"template":"general"', finish_reason="length")

    client._client.chat.completions.create = fake_create  # type: ignore[attr-defined]

    with pytest.raises(StructuredOutputError):
        _run(
            client.complete(
                messages=[{"role": "user", "content": "hello"}],
                model="gemini-2.5-pro",
                max_tokens=3000,
                temperature=0.0,
                response_format=StructuredResponse,
            )
        )

    assert captured_max_tokens == [3000, min(max(3000 * 2, 3001), _MAX_RETRY_TOKENS)]
