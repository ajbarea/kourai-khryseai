"""Shared fixtures for integration tests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.image import DockerImage
from testcontainers.core.network import Network
from testcontainers.core.waiting_utils import wait_for_logs

if TYPE_CHECKING:
    from collections.abc import Generator


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
        wait_for_logs(container, "LiteLLM: Proxy listening on")
        yield container


@pytest.fixture(scope="session")
def agent_build_args() -> dict[str, dict[str, str]]:
    """Common build arguments for agent images."""
    return {
        "hephaestus": {"HOST_TYPE": "agent", "PACKAGE_NAME": "hephaestus", "PORT": "10000"},
        "metis": {"HOST_TYPE": "agent", "PACKAGE_NAME": "metis", "PORT": "10001"},
        "techne": {"HOST_TYPE": "agent", "PACKAGE_NAME": "techne", "PORT": "10002"},
        "dokimasia": {"HOST_TYPE": "agent", "PACKAGE_NAME": "dokimasia", "PORT": "10003"},
        "kallos": {"HOST_TYPE": "agent", "PACKAGE_NAME": "kallos", "PORT": "10004"},
        "mneme": {"HOST_TYPE": "agent", "PACKAGE_NAME": "mneme", "PORT": "10005"},
    }


def _build_agent_image(agent_name: str, args: dict[str, str]) -> Generator[DockerImage, None, None]:
    """Helper to build an agent image using DockerImage context manager."""
    with DockerImage(
        path=".",
        dockerfile_path="docker/host.Dockerfile",
        tag=f"kourai-{agent_name}:test",
        buildargs=args,
    ) as image:
        yield image


@pytest.fixture(scope="session")
def mneme_image(agent_build_args) -> Generator[DockerImage, None, None]:
    yield from _build_agent_image("mneme", agent_build_args["mneme"])


@pytest.fixture(scope="session")
def hephaestus_image(agent_build_args) -> Generator[DockerImage, None, None]:
    yield from _build_agent_image("hephaestus", agent_build_args["hephaestus"])


@pytest.fixture(scope="session")
def metis_image(agent_build_args) -> Generator[DockerImage, None, None]:
    yield from _build_agent_image("metis", agent_build_args["metis"])


@pytest.fixture(scope="session")
def techne_image(agent_build_args) -> Generator[DockerImage, None, None]:
    yield from _build_agent_image("techne", agent_build_args["techne"])


@pytest.fixture(scope="session")
def dokimasia_image(agent_build_args) -> Generator[DockerImage, None, None]:
    yield from _build_agent_image("dokimasia", agent_build_args["dokimasia"])


@pytest.fixture(scope="session")
def kallos_image(agent_build_args) -> Generator[DockerImage, None, None]:
    yield from _build_agent_image("kallos", agent_build_args["kallos"])


def _start_agent_container(
    image: DockerImage, network: Network, alias: str, port: int
) -> DockerContainer:
    """Helper to start an agent container."""
    return (
        DockerContainer(str(image.tag))
        .with_network(network)
        .with_network_aliases(alias)
        .with_exposed_ports(port)
        .with_env("KOURAI_PROVIDER", "openai")
        .with_env("OPENAI_API_BASE", "http://litellm-proxy:4000/v1")
        .with_env("OPENAI_API_KEY", "sk-test")
        .with_env("KOURAI_LOG_LEVEL", "DEBUG")
    )


@pytest.fixture(scope="session")
def mneme_container(
    mneme_image: DockerImage, shared_network, litellm_proxy
) -> Generator[DockerContainer, None, None]:
    with _start_agent_container(mneme_image, shared_network, "mneme", 10005) as c:
        wait_for_logs(c, "📜 Mneme starting")
        yield c


@pytest.fixture(scope="session")
def hephaestus_container(
    hephaestus_image: DockerImage, shared_network, litellm_proxy
) -> Generator[DockerContainer, None, None]:
    with _start_agent_container(hephaestus_image, shared_network, "hephaestus", 10000) as c:
        wait_for_logs(c, "🔥 Hephaestus starting")
        yield c


@pytest.fixture(scope="session")
def metis_container(
    metis_image: DockerImage, shared_network, litellm_proxy
) -> Generator[DockerContainer, None, None]:
    with _start_agent_container(metis_image, shared_network, "metis", 10001) as c:
        wait_for_logs(c, "📐 Metis starting")
        yield c


@pytest.fixture(scope="session")
def techne_container(
    techne_image: DockerImage, shared_network, litellm_proxy
) -> Generator[DockerContainer, None, None]:
    with _start_agent_container(techne_image, shared_network, "techne", 10002) as c:
        wait_for_logs(c, "⚙️ Techne starting")
        yield c


@pytest.fixture(scope="session")
def dokimasia_container(
    dokimasia_image: DockerImage, shared_network, litellm_proxy
) -> Generator[DockerContainer, None, None]:
    with _start_agent_container(dokimasia_image, shared_network, "dokimasia", 10003) as c:
        wait_for_logs(c, "🧪 Dokimasia starting")
        yield c


@pytest.fixture(scope="session")
def kallos_container(
    kallos_image: DockerImage, shared_network, litellm_proxy
) -> Generator[DockerContainer, None, None]:
    with _start_agent_container(kallos_image, shared_network, "kallos", 10004) as c:
        wait_for_logs(c, "✨ Kallos starting")
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
        # Jaeger usually starts quickly, we look for collector start
        wait_for_logs(container, "Reporter starting")
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
        yield container


@pytest.fixture(scope="session")
def context7_container(shared_network: Network) -> Generator[DockerContainer, None, None]:
    """Start context7-mcp container."""
    username = os.getenv("DOCKER_HUB_USERNAME", "ajb6289")
    image = f"{username}/kourai-khryseai:context7-mcp"
    with (
        DockerContainer(image)
        .with_network(shared_network)
        .with_network_aliases("context7-mcp")
        .with_exposed_ports(3001) as container
    ):
        wait_for_logs(container, "Server listening on port 3001")
        yield container


@pytest.fixture(scope="session")
def memory_mcp_container(shared_network: Network) -> Generator[DockerContainer, None, None]:
    """Start memory-mcp container."""
    username = os.getenv("DOCKER_HUB_USERNAME", "ajb6289")
    image = f"{username}/kourai-khryseai:memory-mcp"
    with (
        DockerContainer(image)
        .with_network(shared_network)
        .with_network_aliases("memory-mcp")
        .with_exposed_ports(5000, 5001) as container
    ):
        # Wait for actual readiness signal in logs
        wait_for_logs(container, "Memory MCP SSE ready on port 5001")
        yield container
