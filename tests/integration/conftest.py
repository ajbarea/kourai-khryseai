"""Shared fixtures for integration tests."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network
from testcontainers.core.waiting_utils import wait_for_logs

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)

# Registry where production images are pushed
_REGISTRY_USER = os.getenv("DOCKER_HUB_USERNAME", "ajb6289")
_REGISTRY_REPO = "kourai-khryseai"

# Container registry for log capture on test failure
_containers_registry: dict[str, DockerContainer] = {}


def _registry_image(tag: str) -> str:
    """Return the full registry image reference for a given tag."""
    return f"{_REGISTRY_USER}/{_REGISTRY_REPO}:{tag}"


def register_container(name: str, container: DockerContainer) -> None:
    """Register a container for log capture on test failure."""
    _containers_registry[name] = container


def capture_container_logs(test_name: str) -> None:
    """Capture logs from all registered containers and save to files."""
    logs_dir = Path("logs/containers")
    logs_dir.mkdir(parents=True, exist_ok=True)

    for container_name, container in _containers_registry.items():
        try:
            logs_bytes, _ = container.get_logs()
            logs = logs_bytes.decode("utf-8", errors="ignore")
            log_file = logs_dir / f"{container_name}_{test_name}.log"
            log_file.write_text(logs, encoding="utf-8")
        except Exception as e:
            logger.exception(f"Failed to capture logs for {container_name}: {e}")


def pytest_runtest_makereport(item, call):
    """Pytest hook to capture container logs on test failure."""
    if call.excinfo is not None:  # Test failed
        test_name = item.name.replace("::", "_")
        capture_container_logs(test_name)


@pytest.fixture(scope="session")
def shared_network() -> Generator[Network, None, None]:
    """Shared Docker network for inter-container communication."""
    with Network() as network:
        yield network


@pytest.fixture(scope="session")
def litellm_proxy(shared_network: Network) -> Generator[DockerContainer, None, None]:
    """Start LiteLLM Proxy with mock configuration."""
    config_path = str(Path(__file__).parent / "litellm_mock_config.yaml")
    with (
        DockerContainer("ghcr.io/berriai/litellm:main-latest")
        .with_network(shared_network)
        .with_network_aliases("litellm-proxy")
        .with_volume_mapping(config_path, "/app/config.yaml")
        .with_command("--config /app/config.yaml")
        .with_exposed_ports(4000) as container
    ):
        wait_for_logs(container, "Uvicorn running on")

        # Poll the HTTP health endpoint to confirm readiness (not just log output)
        host = container.get_container_host_ip()
        port = container.get_exposed_port(4000)
        url = f"http://{host}:{port}/health"
        deadline = time.monotonic() + 30.0
        ready = False

        while time.monotonic() < deadline:
            try:
                resp = httpx.get(url, timeout=2.0)
                if resp.status_code < 500:
                    ready = True
                    break
            except Exception:
                logger.debug("Health check not ready yet, retrying...")
            time.sleep(0.5)

        if not ready:
            logger.warning("LiteLLM proxy HTTP endpoint not responding, proceeding anyway")

        register_container("litellm-proxy", container)
        yield container


def _start_agent_container(image: str, network: Network, alias: str, port: int) -> DockerContainer:
    """Return a configured agent container ready to start. Pulls from the registry."""
    return (
        DockerContainer(image)
        .with_network(network)
        .with_network_aliases(alias)
        .with_exposed_ports(port)
        .with_env("KOURAI_PROVIDER", "openai")
        .with_env("OPENAI_API_BASE", "http://litellm-proxy:4000/v1")
        .with_env("OPENAI_API_KEY", "sk-test")
        # Route anthropic-prefixed models through the proxy too (litellm
        # ignores OPENAI_API_BASE for non-OpenAI providers)
        .with_env("ANTHROPIC_API_KEY", "sk-test")
        .with_env("ANTHROPIC_API_BASE", "http://litellm-proxy:4000")
        .with_env("KOURAI_LOG_LEVEL", "DEBUG")
        .with_env("KOURAI_MODEL_OVERRIDE", "openai/mock-model")
        .with_env("PYTHONDONTWRITEBYTECODE", "1")
    )


def _wait_for_agent_ready(container: DockerContainer, port: int, timeout: float = 30.0) -> None:
    """Poll the agent card endpoint until the container is serving HTTP requests.

    The 'starting' log is emitted before uvicorn.run() binds the port,
    so we need to verify the HTTP server is actually ready.
    """
    host = container.get_container_host_ip()
    mapped_port = container.get_exposed_port(port)
    url = f"http://{host}:{mapped_port}/.well-known/agent-card.json"
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code == 200:
                return
        except httpx.HTTPError as exc:
            logger.debug("Agent on port %d not ready yet: %s", port, exc)
        time.sleep(0.5)

    logger.warning("Agent on port %d not responding after %.0fs, proceeding anyway", port, timeout)


@pytest.fixture(scope="session")
def mneme_container(
    shared_network: Network, litellm_proxy: DockerContainer
) -> Generator[DockerContainer, None, None]:
    """Start Mneme agent container from registry image."""
    with _start_agent_container(_registry_image("mneme"), shared_network, "mneme", 10005) as c:
        wait_for_logs(c, "📜 Mneme starting")
        _wait_for_agent_ready(c, 10005)
        register_container("mneme", c)
        yield c


@pytest.fixture(scope="session")
def hephaestus_container(
    shared_network: Network, litellm_proxy: DockerContainer
) -> Generator[DockerContainer, None, None]:
    """Start Hephaestus orchestrator container from registry image."""
    with _start_agent_container(
        _registry_image("hephaestus"), shared_network, "hephaestus", 10000
    ) as c:
        wait_for_logs(c, "🔥 Hephaestus starting")
        _wait_for_agent_ready(c, 10000)
        register_container("hephaestus", c)
        yield c


@pytest.fixture(scope="session")
def metis_container(
    shared_network: Network, litellm_proxy: DockerContainer
) -> Generator[DockerContainer, None, None]:
    """Start Metis agent container from registry image."""
    with _start_agent_container(_registry_image("metis"), shared_network, "metis", 10001) as c:
        wait_for_logs(c, "📐 Metis starting")
        _wait_for_agent_ready(c, 10001)
        register_container("metis", c)
        yield c


@pytest.fixture(scope="session")
def techne_container(
    shared_network: Network, litellm_proxy: DockerContainer
) -> Generator[DockerContainer, None, None]:
    """Start Techne agent container from registry image."""
    with _start_agent_container(_registry_image("techne"), shared_network, "techne", 10002) as c:
        wait_for_logs(c, "⚙️ Techne starting")
        _wait_for_agent_ready(c, 10002)
        register_container("techne", c)
        yield c


@pytest.fixture(scope="session")
def dokimasia_container(
    shared_network: Network, litellm_proxy: DockerContainer
) -> Generator[DockerContainer, None, None]:
    """Start Dokimasia agent container from registry image."""
    with _start_agent_container(
        _registry_image("dokimasia"), shared_network, "dokimasia", 10003
    ) as c:
        wait_for_logs(c, "🧪 Dokimasia starting")
        _wait_for_agent_ready(c, 10003)
        register_container("dokimasia", c)
        yield c


@pytest.fixture(scope="session")
def kallos_container(
    shared_network: Network, litellm_proxy: DockerContainer
) -> Generator[DockerContainer, None, None]:
    """Start Kallos agent container from registry image."""
    with _start_agent_container(_registry_image("kallos"), shared_network, "kallos", 10004) as c:
        wait_for_logs(c, "✨ Kallos starting")
        _wait_for_agent_ready(c, 10004)
        register_container("kallos", c)
        yield c


@pytest.fixture(scope="session")
def jaeger_container(shared_network: Network) -> Generator[DockerContainer, None, None]:
    """Start Jaeger container."""
    with (
        DockerContainer("jaegertracing/all-in-one:1.60")
        .with_network(shared_network)
        .with_network_aliases("jaeger")
        .with_exposed_ports(16686, 4317, 4318) as container
    ):
        wait_for_logs(container, "Reporter starting")
        register_container("jaeger", container)
        yield container


@pytest.fixture(scope="session")
def prometheus_container(shared_network: Network) -> Generator[DockerContainer, None, None]:
    """Start Prometheus container."""
    config_path = str((Path(__file__).parent / "../../docker/prometheus.yml").resolve())
    with (
        DockerContainer("prom/prometheus:v2.54.1")
        .with_network(shared_network)
        .with_network_aliases("prometheus")
        .with_volume_mapping(config_path, "/etc/prometheus/prometheus.yml")
        .with_exposed_ports(9090) as container
    ):
        wait_for_logs(container, "Server is ready to receive web requests")
        register_container("prometheus", container)
        yield container


@pytest.fixture(scope="session")
def context7_container(shared_network: Network) -> Generator[DockerContainer, None, None]:
    """Start context7-mcp container from registry image."""
    with (
        DockerContainer(_registry_image("context7-mcp"))
        .with_network(shared_network)
        .with_network_aliases("context7-mcp")
        .with_exposed_ports(3001) as container
    ):
        wait_for_logs(container, "Listening on port 3001")
        register_container("context7-mcp", container)
        yield container


@pytest.fixture(scope="session")
def memory_mcp_container(shared_network: Network) -> Generator[DockerContainer, None, None]:
    """Start memory-mcp container from registry image."""
    with (
        DockerContainer(_registry_image("memory-mcp"))
        .with_network(shared_network)
        .with_network_aliases("memory-mcp")
        .with_exposed_ports(5000, 5001) as container
    ):
        wait_for_logs(container, "ready on port 5001")

        # Poll health endpoint to confirm HTTP readiness
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5000)
        url = f"http://{host}:{port}/health"
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            try:
                resp = httpx.get(url, timeout=2.0)
                if resp.status_code == 200:
                    break
            except httpx.HTTPError as exc:
                logger.debug("memory-mcp health endpoint not ready yet: %s", exc)
            time.sleep(0.5)

        register_container("memory-mcp", container)
        yield container
