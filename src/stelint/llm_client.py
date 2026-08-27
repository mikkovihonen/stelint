"""LLM client for stelint.

Connects to an OpenAI-compatible endpoint for LLM-powered linting checks.
All functions return None when the LLM is not configured or unavailable,
allowing stelint to operate normally without it.

Configuration via environment variables:
    STELINT_LLM_BASE_URL  - OpenAI-compatible API endpoint (e.g. http://llama:9999/v1)
    STELINT_LLM_MODEL     - Model name (default: local-ornith)
    STELINT_LLM_API_KEY   - API key (any non-empty string for local models)
    STELINT_LLM_TYPE      - LLM backend type (e.g. deepseek, vllm, qwen, openrouter).
                            Selects the request body that disables reasoning output.
    STELINT_LLM_THINKING  - Keep reasoning (thinking) output on or off.
                            Values: on/off, true/false, 1/0, yes/no.
                            Unset: a known STELINT_LLM_TYPE disables thinking.
    STELINT_LLM_TIMEOUT   - Request timeout in seconds (default: 60).
                            Raise this for slow local models.
"""

import os
import sys
from typing import Any

_client: Any = None


def get_llm_client():
    """Return an OpenAI-compatible client, or None if not configured.

    The client is cached as a module-level singleton after the first call.
    Returns None immediately if STELINT_LLM_BASE_URL is not set.
    """
    global _client
    if _client is not None:
        return _client

    base_url = os.environ.get("STELINT_LLM_BASE_URL", "").strip()
    if not base_url:
        return None

    try:
        import openai

        api_key = os.environ.get("STELINT_LLM_API_KEY", "") or "sk-no-key"
        timeout = _request_timeout()

        _client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )
        # Validate the connection by listing models.
        _client.models.list()
    except Exception as e:
        print(f"stelint: LLM client initialization failed: {e}", file=sys.stderr)
        _client = None
        return None

    return _client


def _request_timeout() -> float:
    """Return the request timeout in seconds.

    Read from STELINT_LLM_TIMEOUT. Defaults to 60 seconds: long enough for
    slow local models, short enough to fail fast on dead endpoints.
    Invalid values fall back to the default.
    """
    raw = os.environ.get("STELINT_LLM_TIMEOUT", "").strip()
    if not raw:
        return 60.0
    try:
        value = float(raw)
        if value > 0:
            return value
    except ValueError:
        pass
    return 60.0


# Maps STELINT_LLM_TYPE values to the request body that disables reasoning
# (thinking) output for that backend. Backends not listed have no known way
# to disable reasoning.
_REASONING_DISABLE_BODY: dict[str, dict] = {
    "deepseek": {"thinking": {"type": "disabled"}},
    "vllm": {"chat_template_kwargs": {"enable_thinking": False}},
    "qwen": {"enable_thinking": False},
    "openrouter": {"reasoning": {"effort": "none"}},
}

# Warn once per process for unknown STELINT_LLM_TYPE values.
_warned_unknown_llm_type = False

# Accepted STELINT_LLM_THINKING values.
_THINKING_ON_VALUES = {"on", "true", "1", "yes"}
_THINKING_OFF_VALUES = {"off", "false", "0", "no"}

# Warn once per process for invalid STELINT_LLM_THINKING values.
_warned_invalid_thinking = False


def _thinking_enabled() -> bool:
    """Return True when the user asks to keep reasoning output on.

    Read from STELINT_LLM_THINKING (case-insensitive). When the variable
    is unset, thinking follows the STELINT_LLM_TYPE mapping: a known type
    disables thinking. Invalid values fall back to that default.
    """
    global _warned_invalid_thinking
    raw = os.environ.get("STELINT_LLM_THINKING", "").strip().lower()
    if not raw:
        return False
    if raw in _THINKING_ON_VALUES:
        return True
    if raw in _THINKING_OFF_VALUES:
        return False
    if not _warned_invalid_thinking:
        print(
            f"stelint: Invalid STELINT_LLM_THINKING '{raw}'. Use on or off. Value ignored.",
            file=sys.stderr,
        )
        _warned_invalid_thinking = True
    return False


def _reasoning_disable_body() -> dict | None:
    """Return the request body that disables reasoning for the LLM type.

    Reads STELINT_LLM_TYPE (case-insensitive). Known values are listed in
    _REASONING_DISABLE_BODY. Returns None when the variable is unset or
    holds an unknown value, so the request stays unchanged.
    """
    global _warned_unknown_llm_type
    llm_type = os.environ.get("STELINT_LLM_TYPE", "").strip().lower()
    if not llm_type:
        return None
    body = _REASONING_DISABLE_BODY.get(llm_type)
    if body is None and not _warned_unknown_llm_type:
        print(
            f"stelint: Unknown STELINT_LLM_TYPE '{llm_type}'. Known types: {', '.join(sorted(_REASONING_DISABLE_BODY))}. Reasoning output stays enabled.",
            file=sys.stderr,
        )
        _warned_unknown_llm_type = True
    return body


def llm_chat(messages: list[dict[str, str]], max_tokens: int = 500) -> str | None:
    """Send a chat completion request to the configured LLM.

    Args:
        messages: List of message dicts with 'role' and 'content' keys.
        max_tokens: Maximum number of tokens in the response.
            Defaults to 500 to accommodate reasoning models that output
            their thought process before the actual answer.

    Returns:
        The response text (from 'content' or 'reasoning_content') stripped
        of whitespace, or None on any failure.
    """
    client = get_llm_client()
    if client is None:
        return None

    model = os.environ.get("STELINT_LLM_MODEL", "local-ornith")

    # Disable reasoning output when the user wants it off (the default for a
    # known backend type) and the backend type is known.
    create_kwargs: dict[str, Any] = {}
    if not _thinking_enabled():
        extra_body = _reasoning_disable_body()
        if extra_body is not None:
            create_kwargs["extra_body"] = extra_body

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.0,
            **create_kwargs,
        )
        message = response.choices[0].message
        # Prefer 'content' (the actual answer). Fall back to 'reasoning_content'
        # for models that output their thought process in a separate field.
        text = message.content or message.reasoning_content or ""
        return text.strip()
    except Exception as e:
        print(f"stelint: LLM call failed: {e}", file=sys.stderr)
        return None
