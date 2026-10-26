"""Pre-submission audit: secrets, personal data, test-split leakage, README numbers.

    uv run python scripts/audit.py

Exit code 1 if any check finds a problem.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kuralcheck.audit import run_all  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    failed = 0
    for name, findings in run_all().items():
        print(f"[{'PASS' if not findings else 'FAIL'}] {name}")
        for f in findings:
            print(f"       - {f}")
        failed += bool(findings)
    print("All checks passed." if not failed else f"{failed} check(s) need attention.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
