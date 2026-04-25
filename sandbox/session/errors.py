"""Custom exceptions for the sandbox session layer."""


class SessionNotFoundError(Exception):
    """Raised when a session_id is not registered in the SessionManager."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Session {session_id} not found")


class ClientNotReadyError(Exception):
    """Raised when send_message or interrupt is called before the SDK client is initialized."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Session {session_id} client is not yet initialized")
