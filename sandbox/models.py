"""Sandbox-side shared data models.

Types used across handlers live here. Handler-local helper dataclasses
(like `_CmdResult`) stay in the handler files themselves.
"""

from dataclasses import dataclass


@dataclass
class RepoState:
    """Per-sandbox repo state. Created only by `/repo/bootstrap`.

    One sandbox container serves exactly one run, which owns exactly one
    working branch. `working_branch` is set at bootstrap time and never
    changes for the lifetime of the sandbox.
    """

    repo: str
    base_branch: str
    working_branch: str
