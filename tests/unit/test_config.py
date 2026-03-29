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
        assert result == "gemini/gemini-2.0-flash"

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
