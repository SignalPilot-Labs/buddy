"""Config package constants — shared across all containers."""

SANDBOX_REPO_DIR: str = "/home/agentuser/repo"

# Stdout markers emitted by sandbox/connector during startup.
# AF_BOUND: sandbox emits when it binds to a port ({"port": N})
# AF_READY: connector emits after tunnel setup ({"host": str, "port": N})
# AF_QUEUED: emitted when a job is queued ({"backend_id": str})
AF_BOUND_MARKER: str = "AF_BOUND"
AF_READY_MARKER: str = "AF_READY"
AF_QUEUED_MARKER: str = "AF_QUEUED"
