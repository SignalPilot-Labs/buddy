"""Sandbox-side shared data models."""

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


@dataclass
class CmdResult:
    """Result of a subprocess invocation from a sandbox handler."""

    stdout: str
    stderr: str
    exit_code: int
