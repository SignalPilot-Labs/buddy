#!/bin/bash
set -e

# Agent container entrypoint — orchestrator with Docker socket access
# for spawning per-run sandbox containers.

# Grant agentuser access to Docker socket via group membership (no world-writable chmod)
if [ -S /var/run/docker.sock ]; then
    SOCK_GID=$(stat -c '%g' /var/run/docker.sock)
    if ! getent group "$SOCK_GID" > /dev/null 2>&1; then
        groupadd -g "$SOCK_GID" docker
    fi
    DOCKER_GROUP=$(getent group "$SOCK_GID" | cut -d: -f1)
    usermod -aG "$DOCKER_GROUP" agentuser
fi

# Ensure shared data volume is writable by agentuser
if [ -d /data ]; then
    chown -R agentuser:agentuser /data 2>/dev/null || chmod -R a+rw /data 2>/dev/null || true
else
    mkdir -p /data && chown agentuser:agentuser /data
fi

exec gosu agentuser "$@"
