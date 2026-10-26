"""Find benchmark runs in results/: each run is a folder with summary.json (and raw.jsonl)."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kuralcheck.data import results_dir as _results_dir


@dataclass(frozen=True)
class Run:
    path: Path
    summary: dict[str, Any]

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def split(self) -> str | None:
        return self.summary["run"].get("split")

    @property
    def model(self) -> str:
        return next((r["model"] for r in self.summary["overall"]), "")

    @property
    def is_whisper(self) -> bool:
        return self.model.startswith("whisper")

    def records(self) -> list[dict[str, Any]]:
        raw = self.path / "raw.jsonl"
        if not raw.exists():
            return []
        with raw.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]


def list_runs(results_dir: Path | None = None) -> list[Run]:
    """Oldest first (folder names start with the date)."""
    results_dir = results_dir or _results_dir()
    runs = []
    for p in sorted(results_dir.glob("*/summary.json")):
        try:
            runs.append(Run(p.parent, json.loads(p.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, KeyError):
            continue
    return runs


def latest(split: str | None = None, whisper: bool = False, results_dir: Path | None = None) -> Run | None:
    matches = [r for r in list_runs(results_dir) if r.is_whisper == whisper and (split is None or r.split == split)]
    return matches[-1] if matches else None
