"""
LLM client for Web2Actions using litellm.

litellm gives one OpenAI-format interface to 100+ providers (OpenAI, Anthropic,
Gemini, OpenRouter, DeepSeek, Groq, xAI, Bedrock, ...). Model strings are
provider-prefixed (e.g. 'openai/gpt-4o-mini', 'gemini/gemini-2.5-flash') and
API keys are read from the provider's standard env var.

This is a thin wrapper so the rest of Web2Actions has one `chat()` to call and
the provider/model can be switched with a simple string — no code changes.
"""

from typing import Optional

import litellm


def chat(prompt: str, model: str, api_key: Optional[str] = None) -> str:
    """
    Send a chat prompt to the given provider/model and return the reply text.

    model is provider-prefixed, e.g. 'openai/gpt-4o-mini' or
    'gemini/gemini-2.5-flash'. litellm reads the provider's API key from its
    standard env var (OPENAI_API_KEY, GEMINI_API_KEY, ...) unless api_key is
    given explicitly.
    """
    response = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        api_key=api_key,
    )
    return response.choices[0].message.content