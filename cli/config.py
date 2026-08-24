"""
Persistent model configuration for the Web2Actions CLI.

Stores the user's chosen provider/model (and custom aliases) in a TOML config
file at ~/.web2actions/config.toml, mirroring how tools like Hermes keep
settings in a config file while API keys stay in environment variables.

This is what lets a user run `web2actions model openai/gpt-4o-mini` once and
have all later commands use that model without repeating flags.
"""

import os
from typing import Dict, Optional

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".web2actions")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.toml")


def _ensure_dir() -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)


def _read() -> dict:
    """Read the config file into a dict (empty if missing)."""
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        import tomllib
    except ImportError:  # Python < 3.11
        import tomli as tomllib  # type: ignore
    with open(CONFIG_PATH, "rb") as file:
        return tomllib.load(file)


def _write(data: dict) -> None:
    """Write the config dict to the TOML file."""
    _ensure_dir()
    lines = []
    if data.get("model"):
        lines.append(f"model = \"{data['model']}\"")
    if data.get("provider"):
        lines.append(f"provider = \"{data['provider']}\"")
    aliases = data.get("aliases", {})
    if aliases:
        lines.append("")
        lines.append("[aliases]")
        for name, value in aliases.items():
            lines.append(f"{name} = \"{value}\"")
    with open(CONFIG_PATH, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")


def get_model() -> Optional[str]:
    """Return the configured model spec (provider/model), or None."""
    return _read().get("model")


def set_model(model_spec: str) -> None:
    """Persist the default model spec (e.g. 'openai/gpt-4o-mini')."""
    data = _read()
    data["model"] = model_spec
    _write(data)


def get_provider() -> Optional[str]:
    """Return the configured provider, or None."""
    return _read().get("provider")


def set_provider(provider_name: str) -> None:
    """Persist the default provider."""
    data = _read()
    data["provider"] = provider_name
    _write(data)


def get_aliases() -> Dict[str, str]:
    """Return user-defined aliases."""
    return _read().get("aliases", {})


def set_alias(name: str, model_spec: str) -> None:
    """Persist a user-defined alias."""
    data = _read()
    data.setdefault("aliases", {})[name] = model_spec
    _write(data)