#!/bin/bash
set -e

# Fix docker socket permissions so agentuser can use Docker CLI.
# On Docker Desktop (Windows/Mac) the socket is always root:root,
# so we chmod it at runtime before dropping to agentuser.
if [ -S /var/run/docker.sock ]; then
    chmod 666 /var/run/docker.sock
fi

exec gosu agentuser "$@"
