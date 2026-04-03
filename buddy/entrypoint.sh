#!/bin/bash
set -e

# Grant agentuser access to Docker socket via group membership.
# Avoid chmod 666 which would make the socket world-writable.
if [ -S /var/run/docker.sock ]; then
    DOCKER_GID=$(stat -c '%g' /var/run/docker.sock 2>/dev/null || stat -f '%g' /var/run/docker.sock 2>/dev/null)
    groupadd -g "$DOCKER_GID" -o docker 2>/dev/null || true
    usermod -aG docker agentuser 2>/dev/null || chmod 660 /var/run/docker.sock
fi

# Fix repo volume ownership (created as root on first run)
if [ -d /home/agentuser/repo ]; then
    chown agentuser:agentuser /home/agentuser/repo
fi

# Ensure shared data volume is writable by agentuser
if [ -d /data ]; then
    chown -R agentuser:agentuser /data 2>/dev/null || chmod -R a+rw /data 2>/dev/null || true
else
    mkdir -p /data && chown agentuser:agentuser /data
fi

exec gosu agentuser "$@"
