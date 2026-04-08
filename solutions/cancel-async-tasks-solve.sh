#!/bin/bash
set -e

cat > /app/run.py << 'PYEOF'
import asyncio
import signal
from collections.abc import Awaitable, Callable


async def run_tasks(
    tasks: list[Callable[[], Awaitable[None]]],
    max_concurrent: int,
) -> None:
    semaphore = asyncio.Semaphore(max_concurrent)
    running_tasks: set[asyncio.Task] = set()

    async def run_one(task_fn: Callable[[], Awaitable[None]]) -> None:
        async with semaphore:
            await task_fn()

    loop = asyncio.get_running_loop()
    cancelled = asyncio.Event()

    def handle_sigint() -> None:
        cancelled.set()
        for t in running_tasks:
            t.cancel()

    loop.add_signal_handler(signal.SIGINT, handle_sigint)

    try:
        for task_fn in tasks:
            if cancelled.is_set():
                break
            t = asyncio.create_task(run_one(task_fn))
            running_tasks.add(t)
            t.add_done_callback(running_tasks.discard)

        # Wait for all tasks to complete or be cancelled
        if running_tasks:
            await asyncio.gather(*running_tasks, return_exceptions=True)
    except asyncio.CancelledError:
        pass
    finally:
        loop.remove_signal_handler(signal.SIGINT)
PYEOF

echo "run.py written"
cat /app/run.py
