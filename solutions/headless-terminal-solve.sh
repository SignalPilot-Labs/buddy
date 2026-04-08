#!/bin/bash
set -e

cat > /app/headless_terminal.py << 'PYTHON_EOF'
import subprocess
import time
import uuid

from base_terminal import BaseTerminal

NEWLINE_CHAR = "\n"
TMUX_ENTER_KEY = "Enter"


class HeadlessTerminal(BaseTerminal):
    def __init__(self) -> None:
        self._session_id = str(uuid.uuid4())
        subprocess.run(
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                self._session_id,
                "bash",
                "--login",
                "-i",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def send_keystrokes(self, keystrokes: str, wait_sec: float = 0.0) -> None:
        """
        Sends keystrokes to the terminal.

        Args:
            keystrokes: The keystrokes to send to the terminal.
            wait_sec: The number of seconds to wait for the command to complete.
        """
        self._dispatch_keystrokes(keystrokes)
        time.sleep(wait_sec)

    def _dispatch_keystrokes(self, keystrokes: str) -> None:
        segments = keystrokes.split(NEWLINE_CHAR)
        for index, segment in enumerate(segments):
            if segment:
                self._send_literal(segment)
            if index < len(segments) - 1:
                self._send_key(TMUX_ENTER_KEY)

    def _send_literal(self, text: str) -> None:
        subprocess.run(
            ["tmux", "send-keys", "-t", self._session_id, "-l", text],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _send_key(self, key: str) -> None:
        subprocess.run(
            ["tmux", "send-keys", "-t", self._session_id, key],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
PYTHON_EOF

echo "headless_terminal.py written to /app/headless_terminal.py"
