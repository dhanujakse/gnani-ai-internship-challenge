"""Print planned paid API calls before a run; ask for confirmation above a limit (the project notes rule)."""

import sys
from collections.abc import Callable

CONFIRM_ABOVE = 100


def confirm_calls(
    n_new: int,
    what: str,
    yes: bool = False,
    limit: int = CONFIRM_ABOVE,
    ask: Callable[[str], str] = input,
    interactive: bool | None = None,
) -> bool:
    print(f"Planned new {what} calls: {n_new} (cached calls are free)")
    if n_new <= limit or yes:
        return True
    interactive = sys.stdin.isatty() if interactive is None else interactive
    if not interactive:
        print(f"More than {limit} calls: re-run with --yes to confirm.")
        return False
    return ask(f"Make {n_new} {what} calls? [y/N] ").strip().lower() in ("y", "yes")
