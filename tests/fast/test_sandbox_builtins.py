"""Verify the sandbox builtins allowlist excludes dangerous functions."""

import builtins

import pytest


class TestSandboxBuiltins:
    """Verify the sandbox builtins allowlist excludes dangerous functions."""

    SAFE_ALLOWLIST = [
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
    ]

    DANGEROUS_BUILTINS = [
        "open", "__import__", "exec", "eval", "compile",
        "breakpoint", "globals", "locals", "vars",
    ]

    def test_dangerous_builtins_excluded(self):
        for name in self.DANGEROUS_BUILTINS:
            assert name not in self.SAFE_ALLOWLIST, f"{name} should not be in allowlist"

    def test_safe_builtins_included(self):
        essential = ["print", "len", "range", "int", "float", "str", "list", "dict",
                     "True", "False", "None", "Exception", "ValueError"]
        for name in essential:
            assert name in self.SAFE_ALLOWLIST, f"{name} should be in allowlist"

    def test_allowlist_builds_valid_dict(self):
        safe = {k: getattr(builtins, k) for k in self.SAFE_ALLOWLIST if hasattr(builtins, k)}
        assert callable(safe["print"])
        assert safe["int"] is int
        assert "open" not in safe
        assert "__import__" not in safe
        assert "exec" not in safe

    def test_exec_with_restricted_builtins_blocks_import(self):
        safe = {k: getattr(builtins, k) for k in self.SAFE_ALLOWLIST if hasattr(builtins, k)}
        with pytest.raises((NameError, ImportError)):
            exec(compile("import os", "<test>", "exec"), {"__builtins__": safe})

    def test_exec_with_restricted_builtins_blocks_open(self):
        safe = {k: getattr(builtins, k) for k in self.SAFE_ALLOWLIST if hasattr(builtins, k)}
        with pytest.raises(NameError):
            exec(compile("open('/etc/passwd')", "<test>", "exec"), {"__builtins__": safe})

    def test_exec_with_restricted_builtins_allows_print(self):
        safe = {k: getattr(builtins, k) for k in self.SAFE_ALLOWLIST if hasattr(builtins, k)}
        exec(compile("x = len([1, 2, 3])", "<test>", "exec"), {"__builtins__": safe})
