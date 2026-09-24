"""LLM provider adapters.

Every provider implements one method — ``generate_json(system_prompt, user_prompt, schema)``
— and turns any failure into ``AIProviderError(reason)``. The planner treats every such error
the same way: log it, count it and fall back to the rule-based engine.

* ``AnthropicProvider``        — Claude through the official ``anthropic`` SDK, with
                                 structured JSON output and server-side refusal fallbacks.
* ``OpenAICompatibleProvider`` — any OpenAI-style Chat Completions API over HTTPS: Google
                                 Gemini (free tier), Groq, OpenRouter, or a local Ollama.

API keys are read from configuration (environment variables), never from source code.
"""

import logging
from typing import Protocol

import httpx

from ai_engine.prompts import schema_instructions

logger = logging.getLogger("diet_planner.ai")

# Claude models whose safety classifiers support server-side refusal fallbacks.
REFUSAL_FALLBACK_MODEL_PREFIXES = ("claude-opus-5", "claude-fable-5")
REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AIProviderError(Exception):
    """The provider could not produce an answer; ``reason`` is a short machine-readable code."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class LLMProvider(Protocol):
    name: str
    model: str

    def generate_json(self, system_prompt: str, user_prompt: str, schema: dict) -> str: ...


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        *,
        model: str,
        effort: str | None = "low",
        timeout: float = 45.0,
        api_key: str | None = None,
        client=None,
    ) -> None:
        try:
            import anthropic
        except ImportError as exc:  # the rule-based engine keeps working without the SDK
            raise AIProviderError("sdk_missing") from exc
        self._sdk = anthropic
        self.model = model
        self.effort = effort
        # api_key=None lets the SDK resolve credentials itself (ANTHROPIC_API_KEY, a profile…).
        # One retry keeps a user's wait bounded; the rule-based fallback covers the rest.
        self.client = client or anthropic.Anthropic(api_key=api_key, timeout=timeout,
                                                    max_retries=1)
        self.use_refusal_fallbacks = model.startswith(REFUSAL_FALLBACK_MODEL_PREFIXES)

    def generate_json(self, system_prompt: str, user_prompt: str, schema: dict) -> str:
        sdk = self._sdk
        output_config: dict = {"format": {"type": "json_schema", "schema": schema}}
        if self.effort:
            output_config["effort"] = self.effort  # low effort: quick answers for a web request
        extra: dict = {}
        if self.use_refusal_fallbacks:
            # If a safety classifier declines, the API retries on a fallback model itself.
            extra = {"betas": [REFUSAL_FALLBACK_BETA], "fallbacks": "default"}

        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                output_config=output_config,
                **extra,
            )
        except sdk.AuthenticationError as exc:
            raise AIProviderError("authentication_failed") from exc
        except sdk.PermissionDeniedError as exc:
            raise AIProviderError("permission_denied") from exc
        except sdk.RateLimitError as exc:
            raise AIProviderError("rate_limited") from exc
        except sdk.APITimeoutError as exc:  # subclass of APIConnectionError: check it first
            raise AIProviderError("timeout") from exc
        except sdk.APIConnectionError as exc:
            raise AIProviderError("network_error") from exc
        except sdk.APIStatusError as exc:
            raise AIProviderError(f"api_error_{exc.status_code}") from exc

        # Check why generation stopped before reading the content.
        if response.stop_reason == "refusal":
            raise AIProviderError("refused")
        if response.stop_reason == "max_tokens":
            raise AIProviderError("truncated")
        text = "".join(block.text for block in response.content if block.type == "text")
        if not text.strip():
            raise AIProviderError("empty_response")
        logger.info("Claude answered", extra={"ai_model": response.model,
                                              "output_tokens": response.usage.output_tokens})
        return text


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 45.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.http = http_client or httpx.Client(timeout=timeout)

    def generate_json(self, system_prompt: str, user_prompt: str, schema: dict) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:  # local servers such as Ollama need no key
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                # JSON mode doesn't enforce a schema here, so describe it in the prompt.
                {"role": "user", "content": f"{user_prompt}\n\n{schema_instructions()}"},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.7,
        }
        try:
            response = self.http.post(f"{self.base_url}/chat/completions", json=body,
                                      headers=headers, timeout=self.timeout)
        except httpx.TimeoutException as exc:
            raise AIProviderError("timeout") from exc
        except httpx.HTTPError as exc:
            raise AIProviderError("network_error") from exc

        if response.status_code in (401, 403):
            raise AIProviderError("authentication_failed")
        if response.status_code == 429:
            raise AIProviderError("rate_limited")
        if response.status_code >= 400:
            raise AIProviderError(f"api_error_{response.status_code}")

        try:
            choice = response.json()["choices"][0]
            text = choice["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("invalid_response") from exc
        if choice.get("finish_reason") == "length":
            raise AIProviderError("truncated")
        if not text or not str(text).strip():
            raise AIProviderError("empty_response")
        return str(text)


def create_llm_provider(
    provider: str,
    *,
    anthropic_api_key: str | None = None,
    anthropic_model: str = "claude-opus-5",
    ai_effort: str | None = "low",
    timeout: float = 45.0,
    openai_base_url: str | None = None,
    openai_api_key: str | None = None,
    openai_model: str | None = None,
) -> LLMProvider | None:
    """Build the configured provider, or return None (the rule-based engine is then used)."""
    if provider == "anthropic":
        try:
            return AnthropicProvider(model=anthropic_model, effort=ai_effort, timeout=timeout,
                                     api_key=anthropic_api_key)
        except Exception as exc:  # missing SDK or credentials: degrade, don't crash
            logger.warning("Claude provider unavailable (%s); using the rule-based engine.",
                           getattr(exc, "reason", exc.__class__.__name__))
            return None
    if provider == "openai_compatible":
        if not openai_base_url or not openai_model:
            logger.warning("OPENAI_COMPAT_BASE_URL / OPENAI_COMPAT_MODEL not set; "
                           "using the rule-based engine.")
            return None
        return OpenAICompatibleProvider(base_url=openai_base_url, model=openai_model,
                                        api_key=openai_api_key, timeout=timeout)
    return None
