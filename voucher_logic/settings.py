"""Configuration helpers for provider API keys."""
from __future__ import annotations

import os
from typing import Dict, Optional

try:  # Optional dependency when running outside Streamlit
    import streamlit as st  # type: ignore
except ImportError:  # pragma: no cover - allow tests without Streamlit
    st = None  # type: ignore

from . import models

# Mapping of providers to the environment variable name used for their API key.
PROVIDER_ENV_VARS: Dict[models.ProviderType, str] = {
    models.ProviderType.OPENAI: "OPENAI_API_KEY",
    models.ProviderType.CLAUDE: "ANTHROPIC_API_KEY",
}


def _read_streamlit_secret(name: str) -> Optional[str]:
    """Return a secret managed by Streamlit, if available."""
    if st is None:  # Streamlit not installed or not running
        return None
    try:
        secrets = st.secrets  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - runtime guard when Streamlit not initialised
        return None
    value = secrets.get(name)
    if value is None:
        return None
    return str(value)


def get_secret(name: str) -> Optional[str]:
    """Look up configuration values from env vars first, then Streamlit secrets."""
    env_value = os.getenv(name)
    if env_value:
        return env_value.strip()
    secret_value = _read_streamlit_secret(name)
    if secret_value:
        return secret_value.strip()
    return None


def get_provider_key(provider: models.ProviderType) -> Optional[str]:
    """Return the API key for the requested provider, if configured."""
    env_var = PROVIDER_ENV_VARS.get(provider)
    if not env_var:
        return None
    return get_secret(env_var)


__all__ = ["PROVIDER_ENV_VARS", "get_secret", "get_provider_key"]
