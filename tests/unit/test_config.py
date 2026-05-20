"""Unit tests for kourai_common.config module.

Tests configuration functions and environment-based behavior, using pytest's
monkeypatch fixture for safe, isolated environment variable patching.
"""

import kourai_common.config as config


class TestGetModel:
    """Tests for get_model() function with different providers and tiers."""

    def test_get_model_local_provider(self, monkeypatch):
        """Test PROVIDER == 'local' returns Ollama model from AGENT_MODELS_LOCAL."""
        monkeypatch.setattr("kourai_common.config.PROVIDER", "local")

        result = config.get_model("techne")
        assert result == "ollama/llama3.3:70b"

    def test_get_model_local_provider_dokimasia(self, monkeypatch):
        """Test local provider returns agent-specific Ollama model."""
        monkeypatch.setattr("kourai_common.config.PROVIDER", "local")

        result = config.get_model("dokimasia")
        assert result == "ollama/qwen2.5-coder:32b"

    def test_get_model_anthropic_cheap(self, monkeypatch):
        """Test anthropic provider with cheap tier."""
        monkeypatch.setattr("kourai_common.config.PROVIDER", "anthropic")
        monkeypatch.setattr("kourai_common.config.MODEL_TIER", "cheap")

        result = config.get_model("metis")
        assert result == "anthropic/claude-haiku-4-5-20251001"

    def test_get_model_anthropic_standard(self, monkeypatch):
        """Test anthropic provider with standard tier."""
        monkeypatch.setattr("kourai_common.config.PROVIDER", "anthropic")
        monkeypatch.setattr("kourai_common.config.MODEL_TIER", "standard")

        result = config.get_model("metis")
        assert result == "anthropic/claude-sonnet-4-6"

    def test_get_model_google_cheap(self, monkeypatch):
        """Test google provider with cheap tier."""
        monkeypatch.setattr("kourai_common.config.PROVIDER", "google")
        monkeypatch.setattr("kourai_common.config.MODEL_TIER", "cheap")

        result = config.get_model("hephaestus")
        assert result == "gemini/gemini-2.5-flash-lite"

    def test_get_model_invalid_provider_defaults_anthropic(self, monkeypatch):
        """Test invalid provider falls back to anthropic."""
        monkeypatch.setattr("kourai_common.config.PROVIDER", "invalid_provider")
        monkeypatch.setattr("kourai_common.config.MODEL_TIER", "cheap")

        result = config.get_model("metis")
        assert result == "anthropic/claude-haiku-4-5-20251001"

    def test_get_model_invalid_tier_defaults_cheap(self, monkeypatch):
        """Test invalid tier falls back to cheap tier."""
        monkeypatch.setattr("kourai_common.config.PROVIDER", "anthropic")
        monkeypatch.setattr("kourai_common.config.MODEL_TIER", "invalid_tier")

        result = config.get_model("metis")
        assert result == "anthropic/claude-haiku-4-5-20251001"

    def test_tier_kwarg_overrides_env(self, monkeypatch):
        """Per-call ``tier`` overrides KOURAI_MODEL_TIER for that call only."""
        monkeypatch.setattr("kourai_common.config.PROVIDER", "anthropic")
        monkeypatch.setattr("kourai_common.config.MODEL_TIER", "smart")

        # Even though the env says smart, asking for cheap returns cheap.
        result = config.get_model("metis", tier="cheap")
        assert result == "anthropic/claude-haiku-4-5-20251001"

        # And the env's smart tier still resolves correctly without the kwarg.
        env_result = config.get_model("metis")
        assert env_result == "anthropic/claude-opus-4-7"

    def test_tier_kwarg_none_falls_back_to_env(self, monkeypatch):
        """Default ``tier=None`` reads ``KOURAI_MODEL_TIER`` (backward-compat)."""
        monkeypatch.setattr("kourai_common.config.PROVIDER", "anthropic")
        monkeypatch.setattr("kourai_common.config.MODEL_TIER", "standard")

        # Pre-tier-kwarg behavior preserved when caller doesn't pass it.
        result = config.get_model("metis", tier=None)
        assert result == "anthropic/claude-sonnet-4-6"

    def test_tier_kwarg_unknown_falls_back_to_cheap(self, monkeypatch):
        """Same fallback semantics as MODEL_TIER — unknown tier → cheap."""
        monkeypatch.setattr("kourai_common.config.PROVIDER", "anthropic")
        monkeypatch.setattr("kourai_common.config.MODEL_TIER", "smart")

        result = config.get_model("metis", tier="bogus_tier")
        assert result == "anthropic/claude-haiku-4-5-20251001"

    def test_tier_kwarg_ignored_when_local_provider(self, monkeypatch):
        """Local (Ollama) provider has no tier dimension — ``tier`` is moot."""
        monkeypatch.setattr("kourai_common.config.PROVIDER", "local")

        # Both calls return the same Ollama model; tier is ignored.
        without_tier = config.get_model("techne")
        with_tier = config.get_model("techne", tier="cheap")
        assert without_tier == with_tier

    def test_tier_kwarg_ignored_when_model_override_set(self, monkeypatch):
        """``KOURAI_MODEL_OVERRIDE`` still wins over ``tier`` (test escape hatch)."""
        monkeypatch.setattr("kourai_common.config.PROVIDER", "anthropic")
        monkeypatch.setattr("kourai_common.config.MODEL_TIER", "smart")
        monkeypatch.setenv("KOURAI_MODEL_OVERRIDE", "test/mock-model")

        result = config.get_model("metis", tier="cheap")
        assert result == "test/mock-model"

    def test_metis_smart_tier_is_opus_4_7(self):
        """M9 — Metis's smart tier resolves to the current Anthropic flagship.

        Behaviour-equivalent to ``test_get_model_anthropic_standard`` but
        named to make the M9 bump (Opus 4.6 → 4.7) intentional; if a future
        edit accidentally rolls Metis back, this test names the regression.
        """
        from kourai_common.config import MODELS_SMART

        assert MODELS_SMART["metis"] == "anthropic/claude-opus-4-7"


class TestTierMutation:
    """``/model <tier>`` runtime switching via ``set_tier`` + ``get_tier``."""

    def test_set_tier_mutates_module_state(self, monkeypatch):
        monkeypatch.setattr("kourai_common.config.MODEL_TIER", "cheap")
        config.set_tier("smart")
        assert config.get_tier() == "smart"
        assert config.MODEL_TIER == "smart"

    def test_get_model_sees_set_tier_change(self, monkeypatch):
        """The whole point: ``set_tier`` flips what ``get_model`` returns."""
        monkeypatch.setattr("kourai_common.config.PROVIDER", "anthropic")
        monkeypatch.setattr("kourai_common.config.MODEL_TIER", "cheap")
        assert config.get_model("metis") == "anthropic/claude-haiku-4-5-20251001"
        config.set_tier("smart")
        assert config.get_model("metis") == "anthropic/claude-opus-4-7"

    def test_set_tier_normalizes_case_and_whitespace(self, monkeypatch):
        monkeypatch.setattr("kourai_common.config.MODEL_TIER", "cheap")
        config.set_tier("  SMART  ")
        assert config.get_tier() == "smart"

    def test_set_tier_rejects_unknown(self, monkeypatch):
        import pytest

        monkeypatch.setattr("kourai_common.config.MODEL_TIER", "cheap")
        with pytest.raises(ValueError, match="unknown tier"):
            config.set_tier("opus")
        # State unchanged on rejection.
        assert config.get_tier() == "cheap"


class TestGetAgentUrl:
    """Tests for get_agent_url() function."""

    def test_get_agent_url_returns_docker_service_name(self):
        """Test get_agent_url returns Docker service name format."""
        result = config.get_agent_url("metis")
        assert result == "http://metis:10001/"

    def test_get_agent_url_hephaestus(self):
        """Test get_agent_url for orchestrator agent."""
        result = config.get_agent_url("hephaestus")
        assert result == "http://hephaestus:10000/"

    def test_get_agent_url_port_matches_agent_ports(self):
        """Test get_agent_url port matches AGENT_PORTS mapping."""
        result = config.get_agent_url("kallos")
        assert result == f"http://kallos:{config.AGENT_PORTS['kallos']}/"

    def test_all_agents_have_valid_urls(self):
        """Test all agents in AGENT_PORTS have valid URLs."""
        for agent_name in config.AGENT_PORTS:
            url = config.get_agent_url(agent_name)
            assert url.startswith("http://")
            assert agent_name in url
            assert url.endswith("/")


class TestGetHostAgentUrl:
    """get_host_agent_url() returns the host-reachable URL — localhost + port."""

    def test_returns_localhost_with_agent_port(self):
        assert config.get_host_agent_url("hephaestus") == "http://localhost:10000/"
        assert config.get_host_agent_url("metis") == "http://localhost:10001/"

    def test_does_not_use_docker_service_name(self):
        """Bug guard: must NOT return ``http://hephaestus:10000/`` from the host."""
        url = config.get_host_agent_url("hephaestus")
        assert "hephaestus:" not in url

    def test_all_agents_have_valid_host_urls(self):
        for agent_name in config.AGENT_PORTS:
            url = config.get_host_agent_url(agent_name)
            assert url.startswith("http://localhost:")
            assert url.endswith("/")
