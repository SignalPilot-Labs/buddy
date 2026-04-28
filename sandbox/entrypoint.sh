#!/bin/bash
set -e

# Sandbox container entrypoint — grant Docker socket access when mounted
# via --allow-docker, then drop to agentuser.

if [ -S /var/run/docker.sock ]; then
    SOCK_GID=$(stat -c '%g' /var/run/docker.sock)
    if ! getent group "$SOCK_GID" > /dev/null 2>&1; then
        groupadd -g "$SOCK_GID" docker
    fi
    DOCKER_GROUP=$(getent group "$SOCK_GID" | cut -d: -f1)
    usermod -aG "$DOCKER_GROUP" agentuser
fi

exec gosu agentuser "$@"
