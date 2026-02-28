# Kourai Khryseai — Infrastructure as Code
# This is a modular Terraform setup. Choose your deployment target:
#   - local:  Docker Compose (dev, already handled by docker-compose.yml)
#   - cloud:  Configurable via variables (AWS ECS, GCP Cloud Run, etc.)
#
# For now this sets up the base networking and container registry.
# Agents are deployed as individual containers from the shared Dockerfile.

terraform {
  required_version = ">= 1.5"
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {
  # Default: connects to local Docker daemon
  # Override host for remote Docker or Docker-in-Docker
}

# ──────────────── Variables ────────────────

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "development"
}

variable "agents" {
  description = "Map of agent names to their port numbers"
  type        = map(number)
  default = {
    hephaestus = 10000
    metis      = 10001
    techne     = 10002
    dokimasia  = 10003
    kallos     = 10004
    mneme      = 10005
  }
}

variable "image_tag" {
  description = "Docker image tag for agent builds"
  type        = string
  default     = "latest"
}

# ──────────────── Network ────────────────

resource "docker_network" "kourai" {
  name   = "kourai-${var.environment}"
  driver = "bridge"
}

# ──────────────── Jaeger (Observability) ────────────────

resource "docker_image" "jaeger" {
  name = "jaegertracing/all-in-one:latest"
}

resource "docker_container" "jaeger" {
  name  = "kourai-jaeger-${var.environment}"
  image = docker_image.jaeger.image_id

  networks_advanced {
    name = docker_network.kourai.name
  }

  ports {
    internal = 16686
    external = 16686
  }
  ports {
    internal = 4317
    external = 4317
  }
  ports {
    internal = 4318
    external = 4318
  }

  env = ["COLLECTOR_OTLP_ENABLED=true"]

  restart = "unless-stopped"
}

# ──────────────── Agent Images ────────────────

resource "docker_image" "agent" {
  for_each = var.agents
  name     = "kourai-${each.key}:${var.image_tag}"

  build {
    context    = "${path.module}/../../"
    dockerfile = "docker/agent.Dockerfile"
    build_args = {
      AGENT_NAME = each.key
      PORT       = tostring(each.value)
    }
    tag = ["kourai-${each.key}:${var.image_tag}"]
  }
}

# ──────────────── Agent Containers ────────────────

resource "docker_container" "agent" {
  for_each = var.agents
  name     = "kourai-${each.key}-${var.environment}"
  image    = docker_image.agent[each.key].image_id

  networks_advanced {
    name = docker_network.kourai.name
  }

  ports {
    internal = each.value
    external = each.value
  }

  env = [
    "PORT=${each.value}",
    "OTEL_EXPORTER_OTLP_ENDPOINT=http://kourai-jaeger-${var.environment}:4318",
    "KOURAI_AGENT_HOST=true",
    "KOURAI_LOG_LEVEL=INFO",
  ]

  restart = "unless-stopped"

  depends_on = [docker_container.jaeger]
}

# ──────────────── Outputs ────────────────

output "jaeger_ui" {
  value = "http://localhost:16686"
}

output "agent_urls" {
  value = {
    for name, port in var.agents : name => "http://localhost:${port}/"
  }
}
