"""Tests for the remote provider and FallbackProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from veyron.llm.base import (
    FallbackProvider,
    GenerateChunk,
    GenerateOptions,
    LLMUnavailableError,
    Message,
)
from veyron.llm.remote import RemoteProvider


def _make_stream_context(status_code=200, aiter_lines=None):
    """Build an async context manager that mocks httpx stream responses."""
    class _StreamCtx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    ctx = _StreamCtx()
    ctx.status_code = status_code
    ctx.aiter_lines = aiter_lines or (lambda: iter([]))
    return ctx


class AlwaysAvailableProvider:
    """A stub that is always available and echoes responses."""

    name = "always_available"

    async def is_available(self) -> bool:
        return True

    async def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    async def generate_stream(self, messages, opts):
        yield GenerateChunk(text="hello from fallback", done=True, finish_reason="stop")


class UnavailableProvider:
    """A stub that always raises LLMUnavailableError."""

    name = "unavailable"

    async def is_available(self) -> bool:
        return False

    async def embed(self, text: str) -> list[float]:
        raise LLMUnavailableError("not available")

    async def generate_stream(self, messages, opts):
        if False:
            yield  # makes this an async generator by syntax
        raise LLMUnavailableError("not available")


class _MockClient:
    """Synchronous mock for httpx.AsyncClient used with patch()."""

    def __init__(self):
        self.get = AsyncMock()
        self.stream = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class TestRemoteProvider:
    """Tests for the OpenAI-compatible RemoteProvider."""

    @pytest.mark.asyncio
    async def test_is_available_returns_false_when_no_creds(self):
        provider = RemoteProvider()
        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_returns_false_when_url_empty(self):
        provider = RemoteProvider(api_key="sk-test")
        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_returns_false_when_api_key_empty(self):
        provider = RemoteProvider(base_url="https://api.openai.com/v1")
        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_checks_models_endpoint(self):
        client = _MockClient()
        client.get.return_value.status_code = 200
        client.get.return_value.json = AsyncMock(return_value={"data": [{"id": "gpt-4o"}]})

        provider = RemoteProvider(base_url="https://api.openai.com/v1", api_key="sk-test")
        with patch("httpx.AsyncClient", return_value=client):
            result = await provider.is_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_is_available_returns_false_on_http_error(self):
        client = _MockClient()
        client.get.side_effect = httpx.HTTPError("connection failed")

        provider = RemoteProvider(base_url="https://api.openai.com/v1", api_key="sk-test")
        with patch("httpx.AsyncClient", return_value=client):
            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_is_available_returns_false_on_non_200(self):
        client = _MockClient()
        client.get.return_value.status_code = 401

        provider = RemoteProvider(base_url="https://api.openai.com/v1", api_key="sk-test")
        with patch("httpx.AsyncClient", return_value=client):
            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_generate_stream_raises_on_http_error(self):
        class RaiserCtx:
            async def __aenter__(self):
                raise httpx.HTTPError("connection failed")
            async def __aexit__(self, *args):
                pass

        client = _MockClient()
        client.stream = lambda *a, **kw: RaiserCtx()

        provider = RemoteProvider(base_url="https://api.openai.com/v1", api_key="sk-test")
        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(LLMUnavailableError, match="remote request failed"):
                messages = [Message(role="user", content="hello")]
                opts = GenerateOptions()
                async for _ in provider.generate_stream(messages, opts):
                    pass

    @pytest.mark.asyncio
    async def test_generate_stream_parses_text_chunks(self):
        lines = [
            'data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}',
            'data: {"choices":[{"delta":{"content":" world"},"finish_reason":null}]}',
            'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
            "data: [DONE]",
        ]

        async def mock_aiter_lines():
            for line in lines:
                yield line

        ctx = _make_stream_context(status_code=200, aiter_lines=mock_aiter_lines)

        client = _MockClient()
        client.stream = lambda *a, **kw: ctx

        provider = RemoteProvider(base_url="https://api.openai.com/v1", api_key="sk-test")
        with patch("httpx.AsyncClient", return_value=client):
            chunks = []
            messages = [Message(role="user", content="hello")]
            opts = GenerateOptions()
            async for chunk in provider.generate_stream(messages, opts):
                chunks.append(chunk)

            texts = [c.text for c in chunks if c.text]
            assert "".join(texts) == "Hello world"
            assert any(c.done for c in chunks)

    @pytest.mark.asyncio
    async def test_generate_stream_parses_tool_calls(self):
        lines = [
            'data: {"choices":[{"delta":{"tool_calls":[{"id":"call_1","type":"function","function":{"name":"get_weather","arguments":"{\\"city\\":\\"Paris\\"}"}}]},"finish_reason":"tool_calls"}]}',
            "data: [DONE]",
        ]

        async def mock_aiter_lines():
            for line in lines:
                yield line

        ctx = _make_stream_context(status_code=200, aiter_lines=mock_aiter_lines)

        client = _MockClient()
        client.stream = lambda *a, **kw: ctx

        provider = RemoteProvider(base_url="https://api.openai.com/v1", api_key="sk-test")
        with patch("httpx.AsyncClient", return_value=client):
            chunks = []
            messages = [Message(role="user", content="weather in Paris")]
            opts = GenerateOptions(
                tools=[{"name": "get_weather", "description": "Get weather", "parameters": {"type": "object", "properties": {}}}]
            )
            async for chunk in provider.generate_stream(messages, opts):
                chunks.append(chunk)

            tool_calls = [c.tool_call for c in chunks if c.tool_call]
            assert len(tool_calls) == 1
            assert tool_calls[0]["name"] == "get_weather"
            assert tool_calls[0]["arguments"] == {"city": "Paris"}
            assert any(c.done for c in chunks)


class TestFallbackProvider:
    """Tests for the FallbackProvider chain."""

    @pytest.mark.asyncio
    async def test_primary_success_no_fallback_needed(self):
        primary = AlwaysAvailableProvider()
        fallback = FallbackProvider(primary=primary)
        assert await fallback.is_available() is True

        chunks = []
        async for chunk in fallback.generate_stream([Message(role="user", content="hi")], GenerateOptions()):
            chunks.append(chunk)
        assert len(chunks) > 0
        assert chunks[-1].done

    @pytest.mark.asyncio
    async def test_primary_fails_fallback_not_configured_raises(self):
        primary = UnavailableProvider()
        fallback = FallbackProvider(primary=primary)
        assert await fallback.is_available() is False

        with pytest.raises(LLMUnavailableError):
            async for _ in fallback.generate_stream([Message(role="user", content="hi")], GenerateOptions()):
                pass

    @pytest.mark.asyncio
    async def test_primary_fails_fallback_succeeds(self):
        primary = UnavailableProvider()
        fb = AlwaysAvailableProvider()
        fallback = FallbackProvider(primary=primary, fallback=fb)
        assert await fallback.is_available() is True

        chunks = []
        async for chunk in fallback.generate_stream([Message(role="user", content="hi")], GenerateOptions()):
            chunks.append(chunk)
        assert len(chunks) > 0
        assert chunks[-1].done
        full = "".join(c.text for c in chunks)
        assert "fallback" in full

    @pytest.mark.asyncio
    async def test_embed_falls_back(self):
        primary = UnavailableProvider()
        fb = AlwaysAvailableProvider()
        fallback = FallbackProvider(primary=primary, fallback=fb)
        result = await fallback.embed("test")
        assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_embed_raises_when_no_fallback(self):
        fallback = FallbackProvider(primary=UnavailableProvider())
        with pytest.raises(LLMUnavailableError):
            await fallback.embed("test")

    @pytest.mark.asyncio
    async def test_is_available_primary_ok_without_fallback(self):
        fallback = FallbackProvider(primary=AlwaysAvailableProvider())
        assert await fallback.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_primary_down_fallback_ok(self):
        primary = UnavailableProvider()
        fb = AlwaysAvailableProvider()
        fallback = FallbackProvider(primary=primary, fallback=fb)
        assert await fallback.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_both_down(self):
        primary = UnavailableProvider()
        fb = UnavailableProvider()
        fallback = FallbackProvider(primary=primary, fallback=fb)
        assert await fallback.is_available() is False

    @pytest.mark.asyncio
    async def test_fallback_logs_transition(self, caplog):
        import logging
        caplog.set_level(logging.INFO)

        primary = UnavailableProvider()
        fb = AlwaysAvailableProvider()
        fallback = FallbackProvider(primary=primary, fallback=fb)

        async for _ in fallback.generate_stream([Message(role="user", content="hi")], GenerateOptions()):
            pass

        assert "primary provider unavailable" in caplog.text
        assert "falling back to" in caplog.text


class TestRemoteProviderMessageSerialization:
    """Tests for message serialization to OpenAI format."""

    def test_simple_message(self):
        provider = RemoteProvider()
        msg = Message(role="user", content="hello")
        serialized = provider._serialize_message(msg)
        assert serialized == {"role": "user", "content": "hello"}

    def test_tool_call_message(self):
        provider = RemoteProvider()
        msg = Message(
            role="assistant",
            content="",
            tool_calls=[{"id": "call_1", "name": "get_weather", "arguments": {"city": "Paris"}}],
        )
        serialized = provider._serialize_message(msg)
        assert serialized["role"] == "assistant"
        assert len(serialized["tool_calls"]) == 1
        assert serialized["tool_calls"][0]["function"]["name"] == "get_weather"

    def test_tool_result_message(self):
        provider = RemoteProvider()
        msg = Message(role="tool", content='{"temp": 22}', tool_name="get_weather", tool_call_id="call_1")
        serialized = provider._serialize_message(msg)
        assert serialized["role"] == "tool"
        assert serialized["name"] == "get_weather"
        assert serialized["tool_call_id"] == "call_1"

    def test_to_openai_tool(self):
        provider = RemoteProvider()
        schema = {
            "name": "get_weather",
            "description": "Get weather for a city",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        }
        result = provider._to_openai_tool(schema)
        assert result["type"] == "function"
        assert result["function"]["name"] == "get_weather"
        assert result["function"]["parameters"]["properties"]["city"]["type"] == "string"
