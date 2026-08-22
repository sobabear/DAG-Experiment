import json

import pytest

from impl_comparison.llm import OpenAICompatibleLLM
from impl_comparison.protocol import ModelConfig


def test_llm_from_env_raises_if_provider_or_model_missing(monkeypatch):
    monkeypatch.delenv("IMPL_COMPARISON_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("IMPL_COMPARISON_LLM_MODEL", raising=False)
    monkeypatch.delenv("IMPL_COMPARISON_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("IMPL_COMPARISON_ALLOW_FAKE", raising=False)

    from impl_comparison.llm_config import llm_from_env

    with pytest.raises(ValueError) as excinfo:
        llm_from_env()
    message = str(excinfo.value)
    assert "IMPL_COMPARISON_LLM_PROVIDER" in message
    assert "IMPL_COMPARISON_LLM_MODEL" in message

    monkeypatch.setenv("IMPL_COMPARISON_LLM_PROVIDER", "openai-compatible")
    with pytest.raises(ValueError) as excinfo:
        llm_from_env()
    assert "IMPL_COMPARISON_LLM_MODEL" in str(excinfo.value)

    monkeypatch.delenv("IMPL_COMPARISON_LLM_PROVIDER")
    monkeypatch.setenv("IMPL_COMPARISON_LLM_MODEL", "unit-test-model")
    with pytest.raises(ValueError) as excinfo:
        llm_from_env()
    assert "IMPL_COMPARISON_LLM_PROVIDER" in str(excinfo.value)


def test_llm_from_env_omits_api_key_from_model_config(monkeypatch):
    monkeypatch.setenv("IMPL_COMPARISON_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("IMPL_COMPARISON_LLM_MODEL", "unit-test-model")
    monkeypatch.setenv("IMPL_COMPARISON_LLM_ENDPOINT", "https://example.invalid/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-must-not-appear-in-config")

    from impl_comparison.llm_config import llm_from_env, model_config_from_env

    config = model_config_from_env()
    assert isinstance(config, ModelConfig)
    assert config.provider == "openai-compatible"
    assert config.model == "unit-test-model"
    assert config.endpoint == "https://example.invalid/v1"
    assert "api_key" not in config.extra
    assert "OPENAI_API_KEY" not in config.extra
    dumped = json.dumps(config.to_dict())
    assert "sk-must-not-appear-in-config" not in dumped
    assert "OPENAI_API_KEY" not in dumped

    class Completions:
        def create(self, **kwargs):
            return {"choices": [{"message": {"content": "ok"}}]}

    class Client:
        class chat:
            completions = Completions()

    llm = llm_from_env(client=Client())
    assert isinstance(llm, OpenAICompatibleLLM)
    assert llm.config.provider == "openai-compatible"
    assert llm.config.model == "unit-test-model"
    assert "api_key" not in llm.config.extra
    llm_dumped = json.dumps(llm.config.to_dict())
    assert "sk-must-not-appear-in-config" not in llm_dumped


@pytest.mark.parametrize("value", ["1", "true", "yes"])
def test_allow_fake_from_env_truthy(value):
    from impl_comparison.llm_config import ENV_ALLOW_FAKE, allow_fake_from_env

    assert allow_fake_from_env({ENV_ALLOW_FAKE: value}) is True


@pytest.mark.parametrize("value", ["", "0", "false"])
def test_allow_fake_from_env_falsey(value):
    from impl_comparison.llm_config import ENV_ALLOW_FAKE, allow_fake_from_env

    assert allow_fake_from_env({ENV_ALLOW_FAKE: value}) is False


def test_allow_fake_from_env_missing_is_false():
    from impl_comparison.llm_config import allow_fake_from_env

    assert allow_fake_from_env({}) is False
