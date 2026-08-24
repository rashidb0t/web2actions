"""
Provider-agnostic LLM backend for the Web2Actions agent (Module 17).

The vendored CLI-Anything-Web harness is designed around Claude Code. This
module lets the same harness be driven by ANY LLM provider via litellm, so the
agent is not tied to Claude. It reuses the same model/provider resolution the
CLI already exposes (`web2actions model`), keeping the whole open-core
provider-agnostic.
"""

from typing import Optional

import litellm


def chat(
    prompt: str,
    model: str,
    api_key: Optional[str] = None,
    system: Optional[str] = None,
) -> str:
    """
    Send a prompt (with an optional system prompt) to the given model via
    litellm and return the text reply.

    model is provider-prefixed, e.g. 'openai/gpt-4o-mini' or
    'gemini/gemini-2.5-flash'. litellm reads the provider API key from its
    standard env var unless api_key is given.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = litellm.completion(model=model, messages=messages, api_key=api_key)
    return response.choices[0].message.content


def resolve_model(spec: Optional[str]) -> str:
    """Return the model to use, from a caller-specified spec or the CLI config."""
    if spec:
        return spec
    try:
        from cli import config
        saved = config.get_model()
        if saved:
            return saved
    except Exception:
        pass
    return "openai/gpt-4o-mini"