"""LLM provider adapters, tested against simulated HTTP responses (no network, no API key).

The Claude adapter runs through the real ``anthropic`` SDK with a mock transport, so the tests
check the exact request we send and how the SDK's typed errors are translated.
"""

import json

import anthropic
import httpx
import httpx2
import pytest

from ai_engine.llm_providers import (
    AIProviderError,
    AnthropicProvider,
    OpenAICompatibleProvider,
    create_llm_provider,
)
from ai_engine.prompts import MEAL_PLAN_JSON_SCHEMA

SYSTEM, USER = "system prompt", "user prompt"


def claude_message(text="{}", stop_reason="end_turn"):
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 12, "output_tokens": 34},
    }


def claude_provider(handler, model="claude-opus-5"):
    client = anthropic.Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return AnthropicProvider(model=model, effort="low", client=client)


# --- Claude (Anthropic SDK) ----------------------------------------------------------------------
def test_claude_request_uses_structured_output_effort_and_refusal_fallbacks():
    seen = {}

    def handler(request):
        seen["beta"] = request.headers.get("anthropic-beta", "")
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json=claude_message('{"ok": true}'))

    text = claude_provider(handler).generate_json(SYSTEM, USER, MEAL_PLAN_JSON_SCHEMA)

    body = seen["body"]
    assert text == '{"ok": true}'
    assert body["model"] == "claude-opus-5"
    assert body["system"] == SYSTEM
    assert body["messages"] == [{"role": "user", "content": USER}]
    assert body["output_config"]["effort"] == "low"
    assert body["output_config"]["format"] == {"type": "json_schema",
                                               "schema": MEAL_PLAN_JSON_SCHEMA}
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen["beta"]


def test_claude_models_without_refusal_classifiers_are_called_without_fallbacks():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json=claude_message())

    claude_provider(handler, model="claude-sonnet-5").generate_json(SYSTEM, USER, {})

    assert "fallbacks" not in seen["body"]


@pytest.mark.parametrize(
    ("status", "error_type", "reason"),
    [
        (401, "authentication_error", "authentication_failed"),
        (403, "permission_error", "permission_denied"),
        (429, "rate_limit_error", "rate_limited"),
        (500, "api_error", "api_error_500"),
        (529, "overloaded_error", "api_error_529"),
    ],
)
def test_claude_http_errors_become_named_fallback_reasons(status, error_type, reason):
    def handler(request):
        return httpx2.Response(status, json={"type": "error",
                                             "error": {"type": error_type, "message": "no"}})

    with pytest.raises(AIProviderError) as error:
        claude_provider(handler).generate_json(SYSTEM, USER, {})

    assert error.value.reason == reason


@pytest.mark.parametrize(
    ("exception", "reason"),
    [(httpx2.ConnectError("offline"), "network_error"), (httpx2.ReadTimeout("slow"), "timeout")],
)
def test_claude_network_problems_become_named_fallback_reasons(exception, reason):
    def handler(request):
        raise exception

    with pytest.raises(AIProviderError) as error:
        claude_provider(handler).generate_json(SYSTEM, USER, {})

    assert error.value.reason == reason


@pytest.mark.parametrize(
    ("stop_reason", "text", "reason"),
    [("refusal", "", "refused"), ("max_tokens", '{"partial": ', "truncated"),
     ("end_turn", "   ", "empty_response")],
)
def test_claude_unusable_answers_are_rejected(stop_reason, text, reason):
    def handler(request):
        return httpx2.Response(200, json=claude_message(text, stop_reason))

    with pytest.raises(AIProviderError) as error:
        claude_provider(handler).generate_json(SYSTEM, USER, {})

    assert error.value.reason == reason


# --- OpenAI-compatible APIs (Gemini, Groq, Ollama…) ----------------------------------------------
def openai_provider(handler, api_key="sk-test"):
    return OpenAICompatibleProvider(
        base_url="https://llm.example/v1/",
        model="demo-model",
        api_key=api_key,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def chat_completion(content, finish_reason="stop"):
    return {"choices": [{"message": {"role": "assistant", "content": content},
                         "finish_reason": finish_reason}]}


def test_openai_compatible_request_asks_for_json_and_sends_the_key():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=chat_completion('{"ok": true}'))

    text = openai_provider(handler).generate_json(SYSTEM, USER, MEAL_PLAN_JSON_SCHEMA)

    assert text == '{"ok": true}'
    assert seen["url"] == "https://llm.example/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    assert seen["body"]["model"] == "demo-model"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["messages"][0] == {"role": "system", "content": SYSTEM}
    assert "breakfast" in seen["body"]["messages"][1]["content"]  # schema described in prompt


def test_openai_compatible_local_models_need_no_key():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=chat_completion("{}"))

    openai_provider(handler, api_key=None).generate_json(SYSTEM, USER, {})

    assert seen["auth"] is None


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (httpx.Response(401, json={"error": "bad key"}), "authentication_failed"),
        (httpx.Response(429, json={"error": "slow down"}), "rate_limited"),
        (httpx.Response(503, text="unavailable"), "api_error_503"),
        (httpx.Response(200, json={"unexpected": True}), "invalid_response"),
        (httpx.Response(200, json=chat_completion('{"cut', "length")), "truncated"),
        (httpx.Response(200, json=chat_completion("")), "empty_response"),
    ],
)
def test_openai_compatible_failures_become_named_fallback_reasons(response, reason):
    with pytest.raises(AIProviderError) as error:
        openai_provider(lambda request: response).generate_json(SYSTEM, USER, {})

    assert error.value.reason == reason


def test_openai_compatible_timeouts_become_a_named_fallback_reason():
    def handler(request):
        raise httpx.ReadTimeout("slow")

    with pytest.raises(AIProviderError) as error:
        openai_provider(handler).generate_json(SYSTEM, USER, {})

    assert error.value.reason == "timeout"


# --- Factory -------------------------------------------------------------------------------------
def test_factory_returns_no_provider_for_the_rule_based_setting():
    assert create_llm_provider("rule_based") is None


def test_factory_returns_no_provider_when_openai_compatible_settings_are_missing():
    assert create_llm_provider("openai_compatible", openai_base_url=None,
                               openai_model="m") is None


def test_factory_builds_the_claude_provider_with_the_configured_model():
    provider = create_llm_provider("anthropic", anthropic_api_key="test-key",
                                   anthropic_model="claude-opus-5", ai_effort="medium")

    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "claude-opus-5"
    assert provider.effort == "medium"
