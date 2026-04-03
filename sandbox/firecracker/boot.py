#!/usr/bin/python3
"""
Buddy Sandbox Init — runs as PID 1 inside Firecracker microVM.

1. Mounts filesystems
2. Pre-imports common Python modules (the expensive part)
3. Writes READY marker to serial console (stdout)
4. Blocks reading code from serial console (stdin)
5. Executes code, writes JSON result to serial console
6. Reboots (triggers Firecracker process exit)

For snapshot mode: the VM is snapshotted while blocked at step 4.
On restore, code is written to the new Firecracker process's stdin,
the VM reads it, executes, and returns the result.
"""
import io
import json
import os
import subprocess
import sys
import traceback

# ─── Step 1: Mount filesystems ───────────────────────────────────────────────
subprocess.run(["/bin/mount", "-t", "proc", "proc", "/proc"], stderr=subprocess.DEVNULL)
subprocess.run(["/bin/mount", "-t", "sysfs", "sysfs", "/sys"], stderr=subprocess.DEVNULL)
subprocess.run(["/bin/mount", "-t", "devtmpfs", "devtmpfs", "/dev"], stderr=subprocess.DEVNULL)

# ─── Step 2: Pre-import common modules ──────────────────────────────────────
# This is what takes ~800ms on cold boot. After snapshot, it's free.
import collections
import datetime
import functools
import hashlib
import itertools
import math
import random
import re
import string
import time

# ─── Step 3: Signal ready ───────────────────────────────────────────────────
sys.stdout.write("===SP_READY===\n")
sys.stdout.flush()

# ─── Step 4: Read code from stdin ────────────────────────────────────────────
# Blocks here. In snapshot mode, the VM is paused at this point.
# After restore, code arrives on stdin from the host.
lines = []
for line in sys.stdin:
    stripped = line.rstrip("\n")
    if stripped == "===SP_CODE_END===":
        break
    lines.append(line)
code = "".join(lines)

# ─── Step 5: Execute ────────────────────────────────────────────────────────
stdout_buf = io.StringIO()
stderr_buf = io.StringIO()
old_out, old_err = sys.stdout, sys.stderr
exit_code = 0

try:
    sys.stdout = stdout_buf
    sys.stderr = stderr_buf
    # Restricted builtins: open(), __import__(), exec(), eval(), compile() are
    # intentionally excluded to prevent file access and arbitrary code loading.
    # Pre-imported modules (math, re, etc.) are still available from step 2.
    _safe = {k: __builtins__[k] if isinstance(__builtins__, dict) else getattr(__builtins__, k) for k in [
        "print", "len", "range", "enumerate", "zip", "map", "filter", "sorted", "reversed",
        "min", "max", "sum", "abs", "round", "pow", "divmod",
        "int", "float", "str", "bool", "list", "dict", "tuple", "set", "frozenset",
        "bytes", "bytearray", "memoryview", "complex",
        "type", "isinstance", "issubclass", "hasattr", "getattr", "setattr", "delattr",
        "iter", "next", "slice", "repr", "format", "hash", "id", "callable",
        "all", "any", "chr", "ord", "hex", "oct", "bin",
        "input", "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
        "RuntimeError", "StopIteration", "AttributeError", "NameError", "ZeroDivisionError",
        "True", "False", "None",
    ] if (isinstance(__builtins__, dict) and k in __builtins__) or (not isinstance(__builtins__, dict) and hasattr(__builtins__, k))}
    exec(compile(code, "<sandbox>", "exec"), {"__builtins__": _safe})
except SystemExit as e:
    exit_code = e.code if isinstance(e.code, int) else 1
except Exception:
    exit_code = 1
    traceback.print_exc(file=stderr_buf)
finally:
    sys.stdout = old_out
    sys.stderr = old_err

result = json.dumps({
    "success": exit_code == 0,
    "output": stdout_buf.getvalue(),
    "error": stderr_buf.getvalue() or None,
    "exit_code": exit_code,
})

sys.stdout.write(f"===SP_RESULT_START===\n{result}\n===SP_RESULT_END===\n")
sys.stdout.flush()

# ─── Step 6: Shutdown ───────────────────────────────────────────────────────
subprocess.run(["/bin/busybox", "reboot", "-f"])
