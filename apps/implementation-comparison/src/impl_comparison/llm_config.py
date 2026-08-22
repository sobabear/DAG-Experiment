"""Shared real-LLM settings from the process environment (never from files)."""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional

from .llm import OpenAICompatibleLLM
from .protocol import ModelConfig

ENV_PROVIDER = "IMPL_COMPARISON_LLM_PROVIDER"
ENV_MODEL = "IMPL_COMPARISON_LLM_MODEL"
ENV_ENDPOINT = "IMPL_COMPARISON_LLM_ENDPOINT"
ENV_ALLOW_FAKE = "IMPL_COMPARISON_ALLOW_FAKE"


def allow_fake_from_env(environ: Optional[Mapping[str, str]] = None) -> bool:
    env = os.environ if environ is None else environ
    value = str(env.get(ENV_ALLOW_FAKE, "")).strip().lower()
    return value in {"1", "true", "yes"}


def model_config_from_env(environ: Optional[Mapping[str, str]] = None) -> ModelConfig:
    """Build ModelConfig from env. Never copies OPENAI_API_KEY into extra."""
    env = os.environ if environ is None else environ
    provider = str(env.get(ENV_PROVIDER, "")).strip()
    model = str(env.get(ENV_MODEL, "")).strip()
    if not provider or not model:
        raise ValueError(
            "research-30 requires {} and {} in the environment. "
            "OPENAI_API_KEY is read by the OpenAI SDK from the process "
            "environment and must not be copied into ModelConfig, files, "
            "logs, or score.json.".format(ENV_PROVIDER, ENV_MODEL)
        )
    endpoint = str(env.get(ENV_ENDPOINT, "")).strip() or None
    return ModelConfig(
        provider=provider,
        model=model,
        endpoint=endpoint,
        extra={},
    )


def llm_from_env(
    environ: Optional[Mapping[str, str]] = None,
    client: Any = None,
) -> OpenAICompatibleLLM:
    """Identical OpenAI-compatible factory for all three systems."""
    config = model_config_from_env(environ)
    return OpenAICompatibleLLM(config, client=client)
