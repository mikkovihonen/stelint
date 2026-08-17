"""LLM client for stelint.

Connects to an OpenAI-compatible endpoint for LLM-powered linting checks.
All functions return None when the LLM is not configured or unavailable,
allowing stelint to operate normally without it.

Configuration via environment variables:
    STELINT_LLM_BASE_URL  - OpenAI-compatible API endpoint (e.g. http://llama:9999/v1)
    STELINT_LLM_MODEL     - Model name (default: local-ornith)
    STELINT_LLM_API_KEY   - API key (any non-empty string for local models)
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

        _client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=30.0,
        )
        # Validate the connection by listing models.
        _client.models.list()
    except Exception as e:
        print(f"stelint: LLM client initialization failed: {e}", file=sys.stderr)
        _client = None
        return None

    return _client


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

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.0,
        )
        message = response.choices[0].message
        # Prefer 'content' (the actual answer). Fall back to 'reasoning_content'
        # for models that output their thought process in a separate field.
        text = message.content or message.reasoning_content or ""
        return text.strip()
    except Exception as e:
        print(f"stelint: LLM call failed: {e}", file=sys.stderr)
        return None
