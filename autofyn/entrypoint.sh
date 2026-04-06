#!/bin/bash
set -e

# Agent container entrypoint — no code execution, just the orchestrator.
# Docker socket and repo volume are no longer in this container.

# Ensure shared data volume is writable by agentuser
if [ -d /data ]; then
    chown -R agentuser:agentuser /data 2>/dev/null || chmod -R a+rw /data 2>/dev/null || true
else
    mkdir -p /data && chown agentuser:agentuser /data
fi

exec gosu agentuser "$@"
