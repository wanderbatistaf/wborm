"""Compatibility helpers for optional terminal dependencies."""

from typing import Iterable, Sequence


def cprint(message, color=None):
    """Fallback-compatible color print."""
    try:
        from termcolor import cprint as termcolor_cprint
    except ImportError:
        print(message)
        return
    termcolor_cprint(message, color)


def tabulate_data(rows: Iterable[Sequence], headers=None, tablefmt: str = "grid") -> str:
    """Render a table with tabulate when available, with a plain fallback."""
    try:
        from tabulate import tabulate
    except ImportError:
        rows = list(rows)
        headers = list(headers or [])
        raw_rows = [headers] + [list(row) for row in rows] if headers else [list(row) for row in rows]
        if not raw_rows:
            return ""
        widths = [max(len(str(row[idx])) for row in raw_rows) for idx in range(len(raw_rows[0]))]

        def format_row(row):
            return " | ".join(str(value).ljust(widths[idx]) for idx, value in enumerate(row))

        lines = []
        if headers:
            lines.append(format_row(headers))
            lines.append("-+-".join("-" * width for width in widths))
        lines.extend(format_row(row) for row in rows)
        return "\n".join(lines)
    return tabulate(rows, headers=headers, tablefmt=tablefmt)


def terminal_colors():
    """Return terminal colors with a no-op fallback when colorama is unavailable."""
    try:
        from colorama import Fore, Style
        return Fore, Style
    except ImportError:
        class _Empty:
            BLACK = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
            RESET_ALL = ""

        return _Empty(), _Empty()
