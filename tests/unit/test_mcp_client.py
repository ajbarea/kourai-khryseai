"""Unit tests for MCPToolkit — MCP server registry and agent assignments."""

import pytest

from kourai_common.mcp_client import (
    MCPToolkit,
    MCPUnavailable,
    ServerConfig,
    get_mcp_toolkit,
)


def test_server_config_creation():
    """Test creating a server configuration."""
    config = ServerConfig(
        name="github",
        enabled=True,
        endpoint="https://api.github.com",
        env_vars={"GITHUB_TOKEN": "test_token"},
        timeout=60,
    )
    assert config.name == "github"
    assert config.enabled is True
    assert config.env_vars["GITHUB_TOKEN"] == "test_token"  # noqa: S105
    assert config.timeout == 60


def test_toolkit_register_server():
    """Test registering an MCP server."""
    toolkit = MCPToolkit()
    toolkit.register_server("github", enabled=True, endpoint="https://api.github.com")

    assert "github" in toolkit.server_registry
    config = toolkit.server_registry["github"]
    assert config.enabled is True
    assert config.endpoint == "https://api.github.com"


def test_toolkit_assign_servers():
    """Test assigning servers to an agent."""
    toolkit = MCPToolkit()
    toolkit.assign_servers("techne", ["context7", "github"], fallback_mode="subprocess")

    assert "techne" in toolkit.agent_assignments
    assignment = toolkit.agent_assignments["techne"]
    assert assignment.servers == ["context7", "github"]
    assert assignment.fallback_mode == "subprocess"


def test_get_available_server_first_enabled():
    """Test that get_available_server returns the first enabled server."""
    toolkit = MCPToolkit()
    toolkit.register_server("context7", enabled=True)
    toolkit.register_server("context_hub", enabled=True)
    toolkit.assign_servers("metis", ["context7", "context_hub"])

    server = toolkit.get_available_server("metis")
    assert server is not None
    assert server.name == "context7"


def test_get_available_server_skip_disabled():
    """Test that disabled servers are skipped."""
    toolkit = MCPToolkit()
    toolkit.register_server("context7", enabled=False)
    toolkit.register_server("context_hub", enabled=True)
    toolkit.assign_servers("metis", ["context7", "context_hub"])

    server = toolkit.get_available_server("metis")
    assert server is not None
    assert server.name == "context_hub"


def test_get_available_server_none_available():
    """Test that None is returned when no servers are available."""
    toolkit = MCPToolkit()
    toolkit.register_server("context7", enabled=False)
    toolkit.assign_servers("metis", ["context7"])

    server = toolkit.get_available_server("metis")
    assert server is None


def test_get_available_server_not_assigned():
    """Test that None is returned for agents with no assignments."""
    toolkit = MCPToolkit()

    server = toolkit.get_available_server("unknown_agent")
    assert server is None


def test_get_tool_unavailable():
    """Test that get_tool raises MCPUnavailable when no servers are available."""
    toolkit = MCPToolkit()
    toolkit.register_server("github", enabled=False)
    toolkit.assign_servers("techne", ["github"])

    with pytest.raises(MCPUnavailable):
        toolkit.get_tool("techne", "search_code")


def test_disable_enable_server():
    """Test disabling and re-enabling servers."""
    toolkit = MCPToolkit()
    toolkit.register_server("github", enabled=True)

    toolkit.disable_server("github")
    assert not toolkit.is_server_enabled("github")

    toolkit.enable_server("github")
    assert toolkit.is_server_enabled("github")


def test_is_server_enabled():
    """Test checking if a server is enabled."""
    toolkit = MCPToolkit()
    toolkit.register_server("github", enabled=True)
    toolkit.register_server("gitlab", enabled=False)

    assert toolkit.is_server_enabled("github") is True
    assert toolkit.is_server_enabled("gitlab") is False
    assert toolkit.is_server_enabled("nonexistent") is False


def test_default_registry_initialization():
    """Test that default registry is properly initialized."""
    toolkit = get_mcp_toolkit()

    # Check some servers are registered
    assert toolkit.is_server_enabled("github")
    assert toolkit.is_server_enabled("context7")
    assert toolkit.is_server_enabled("brave_search")

    # Check some assignments exist
    assert "techne" in toolkit.agent_assignments
    assert "mneme" in toolkit.agent_assignments
    assert "aletheia" in toolkit.agent_assignments

    # Verify Techne has context7 first (for documentation lookup)
    techne_servers = toolkit.agent_assignments["techne"].servers
    assert techne_servers[0] == "context7"

    # Verify Aletheia has brave_search
    aletheia_servers = toolkit.agent_assignments["aletheia"].servers
    assert "brave_search" in aletheia_servers


def test_mcp_unavailable_exception():
    """Test MCPUnavailable exception is properly defined."""
    with pytest.raises(MCPUnavailable) as exc_info:
        raise MCPUnavailable("Test error message")

    assert "Test error message" in str(exc_info.value)
