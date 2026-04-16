#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/.autofyn"
PYTHON_VERSION=3.12
NODE_VERSION=22
UV_VERSION=0.11
GVISOR_VERSION=20260323.0
DOCKER_CLI_VERSION=27.5.1
POSTGRES_VERSION=16
UBUNTU_VERSION=22.04

# Compose interpolates ${AGENT_INTERNAL_SECRET:?...} in docker-compose.yml at
# build time. Pass --env-file explicitly so the .env seeded by install.sh/up.sh
# is always picked up, regardless of Compose's project-dir detection.
ENV_FILE="$HOME/.autofyn/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "[build] .env not found at $ENV_FILE — run install.sh or up.sh first" >&2
    exit 1
fi

docker compose --env-file "$ENV_FILE" build \
    --build-arg PYTHON_VERSION="$PYTHON_VERSION" \
    --build-arg NODE_VERSION="$NODE_VERSION" \
    --build-arg UV_VERSION="$UV_VERSION" \
    --build-arg GVISOR_VERSION="$GVISOR_VERSION" \
    --build-arg DOCKER_CLI_VERSION="$DOCKER_CLI_VERSION" \
    --build-arg POSTGRES_VERSION="$POSTGRES_VERSION" \
    --build-arg UBUNTU_VERSION="$UBUNTU_VERSION"
