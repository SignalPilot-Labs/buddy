# Code Rules

These rules are mandatory. All AI agents (planner, builder, reviewer, etc.) must follow them. No exceptions.

## Imports

- All imports at the top of the file. No inline imports inside functions or methods.
- Absolute imports from the package root. No relative imports (`from . import`). No `sys.path` hacks.
- `__init__.py` files must be empty. No code, no re-exports, no `__all__`.

## Constants

- All magic values (numbers, strings, URLs, ports, timeouts, limits) go in a dedicated `constants.py`, `models.py` or `sh` file.
- No magic values inline in code. No default values for function parameters — pass constants explicitly at the call site.

## Types

- Every function must have full type annotations (parameters and return type).
- Run `pyright` before considering work done. It must pass at `basic` level (configured in `pyrightconfig.json`).

## No Defensive Coding

- No `hasattr()`, `isinstance()` checks for duck typing, `getattr()` with defaults, or `try/except` for control flow.
- Trust your types. If the type system says it's there, it's there. If it might not be, fix the type.

## Architecture

- OOP with clear separation of concerns. One class, one responsibility. One function, one task.
- Orchestrator/executor pattern: orchestrators delegate, executors do work. No god classes.
- Dependency injection: pass dependencies in, don't import and instantiate internally.
- DRY: if logic appears twice, extract it. Common code in base classes or shared helpers.

## Size Limits

- No function longer than 20 lines. Extract helpers.
- No file longer than 400 lines. Split into focused modules.

## Verification

Before finishing any task, run:
```
pyright
ruff check
```
Both must pass clean.
