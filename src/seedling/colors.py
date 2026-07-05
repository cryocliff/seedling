"""
Minimal ANSI color helper. No dependency (no colorama/rich) -- just enough
to make confirmation prompts, warnings, and section headers easier to
scan. Colors are automatically disabled when stdout isn't a real terminal
(e.g. piped/redirected output, CI logs) or when NO_COLOR is set, per
https://no-color.org.
"""

from __future__ import annotations

import os
import sys

_enabled: bool | None = None


def _enable_windows_ansi() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass


def supports_color() -> bool:
    global _enabled
    if _enabled is not None:
        return _enabled
    if os.environ.get("NO_COLOR"):
        _enabled = False
    elif not sys.stdout.isatty():
        _enabled = False
    else:
        if os.name == "nt":
            _enable_windows_ansi()
        _enabled = True
    return _enabled


def _wrap(code: str, text: str) -> str:
    if not supports_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def bold(text: str) -> str:
    return _wrap("1", text)


def dim(text: str) -> str:
    return _wrap("2", text)


def red(text: str) -> str:
    return _wrap("31", text)


def green(text: str) -> str:
    return _wrap("32", text)


def yellow(text: str) -> str:
    return _wrap("33", text)


def cyan(text: str) -> str:
    return _wrap("36", text)


def header(text: str) -> str:
    return bold(cyan(text))


def warn(text: str) -> str:
    return yellow(text)


def danger(text: str) -> str:
    return bold(red(text))


def ok(text: str) -> str:
    return green(text)
