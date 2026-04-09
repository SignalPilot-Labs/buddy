#!/bin/bash
set -e

# Agent container entrypoint — orchestrator with Docker socket access
# for spawning per-run sandbox containers.

# Grant agentuser access to Docker socket if mounted
if [ -S /var/run/docker.sock ]; then
    chmod 666 /var/run/docker.sock
fi

# Ensure shared data volume is writable by agentuser
if [ -d /data ]; then
    chown -R agentuser:agentuser /data 2>/dev/null || chmod -R a+rw /data 2>/dev/null || true
else
    mkdir -p /data && chown agentuser:agentuser /data
fi

exec gosu agentuser "$@"
