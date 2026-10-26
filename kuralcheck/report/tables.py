"""Markdown tables from summary.json only (never hand-typed numbers).

Cells read "12.3 (10.1–14.6)": the metric in % with its bootstrap 95% CI. Each row shows n,
the number of utterances scored.
"""

from typing import Any

from kuralcheck.audio.conditions import CONDITIONS
from kuralcheck.runner import SETTING_LABELS

SOURCE_LABELS = {"real": "Real recordings (colloquial / dialect)", "timbre": "Synthetic (Timbre, standard Tamil)"}
CATEGORY_LABELS = {
    "numbers": "Numbers, money, time",
    "names_places": "Names and places",
    "code_mixed": "Code-mixed English",
    "everyday": "Everyday",
    "colloquial": "Colloquial",
    "dialect": "Dialect",
    "slang": "Slang",
}


def pct(ci: dict[str, Any] | None) -> str:
    if not ci or ci.get("value") is None or ci["value"] != ci["value"]:  # None or NaN
        return "–"
    return f"{100 * ci['value']:.1f} ({100 * ci['low']:.1f}–{100 * ci['high']:.1f})"


def _n_label(ns: list[int]) -> str:
    ns = [n for n in ns if n]
    if not ns:
        return "0"
    return str(ns[0]) if min(ns) == max(ns) else f"{min(ns)}–{max(ns)}"


def matrix(rows: list[dict[str, Any]], row_key: str, row_values: list[str], settings: list[str],
           metric: str, row_labels: dict[str, str]) -> str:  # fmt: skip
    """One table: rows (conditions or categories) x settings."""
    by = {(r[row_key], r["setting"]): r for r in rows}
    head = f"| {row_key.title()} | n | " + " | ".join(f"{s} {SETTING_LABELS.get(s, '')}".strip() for s in settings) + " |"
    lines = [head, "|" + "---|" * (len(settings) + 2)]
    for v in row_values:
        cells = [by.get((v, s)) for s in settings]
        if not any(cells):
            continue
        n = _n_label([c["n"] for c in cells if c])
        if metric == "number_accuracy":
            n = _n_label([c[metric]["n"] for c in cells if c and c.get(metric)])
        values = [pct(c.get(metric)) if c else "–" for c in cells]
        lines.append(f"| {row_labels.get(v, v)} | {n} | " + " | ".join(values) + " |")
    return "\n".join(lines)


def summary_markdown(summary: dict[str, Any], headline_only: bool = False) -> str:
    run = summary["run"]
    settings = run.get("settings") or sorted({r["setting"] for r in summary["overall"]})
    conds = [c for c in CONDITIONS if c in {r["condition"] for r in summary["overall"]}]
    cond_labels = {c: f"{c} {CONDITIONS[c].label}" for c in CONDITIONS}
    models = sorted({r["model"] for r in summary["overall"]})
    out: list[str] = []
    if not headline_only:
        lat = run.get("latency_ms") or {}
        calls = run.get("prisma_calls") or {}
        out += [
            f"# Results: {run.get('split')} split",
            "",
            f"- Date: {run.get('created_at', '')[:10]} · commit `{run.get('git_commit')}`",
            f"- Models: {', '.join(f'{k}={v}' for k, v in (run.get('models') or {}).items())}",
            f"- Utterances: {run.get('n_utterances')} · records: {run.get('n_records')} · failed: {run.get('n_failures')}",
            f"- Prisma calls: {calls.get('unique')} unique ({calls.get('new')} new, {calls.get('from_cache')} cached)",
            f"- Latency per call: p50 {lat.get('p50')} ms · p95 {lat.get('p95')} ms (n={lat.get('n')})",
            f"- Bias words: {run.get('bias_words', {}).get('n')} · lexicon rules: {run.get('lexicon', {}).get('n_rules')}",
            "",
            "Cells: metric in % with bootstrap 95% CI (1000 resamples, seed 42). Lower CER/WER is better.",
            "Small team-made test set: read intervals, not just point values.",
            "",
        ]
    for model in models:
        for source in ("real", "timbre"):
            rows = [r for r in summary["overall"] if r["model"] == model and r["source"] == source]
            if not rows:
                continue
            title = f"{SOURCE_LABELS[source]} · {model}"
            out += [f"## {title}", "", "**CER %** (primary)", "", matrix(rows, "condition", conds, settings, "cer", cond_labels), ""]
            if headline_only:
                continue
            out += ["**WER %**", "", matrix(rows, "condition", conds, settings, "wer", cond_labels), ""]
            if any(r.get("number_accuracy") for r in rows):
                out += ["**Number accuracy %** (higher is better; utterances containing numbers)", "",
                        matrix(rows, "condition", conds, settings, "number_accuracy", cond_labels), ""]  # fmt: skip
            cats = [r for r in summary["by_category"] if r["model"] == model and r["source"] == source]
            for cond in conds:
                crow = [r for r in cats if r["condition"] == cond]
                if crow:
                    out += [f"**CER % by category · {cond_labels[cond]}**", "",
                            matrix(crow, "category", list(CATEGORY_LABELS), settings, "cer", CATEGORY_LABELS), ""]  # fmt: skip
        dialect_rows = [r for r in summary.get("by_dialect", []) if r["model"] == model]
        if dialect_rows and not headline_only:
            dialects = sorted({r["dialect"] for r in dialect_rows})
            for cond in conds:
                drow = [r for r in dialect_rows if r["condition"] == cond]
                if drow:
                    out += [f"**Real recordings: CER % by dialect · {cond_labels[cond]}**", "",
                            matrix(drow, "dialect", dialects, settings, "cer", {}), ""]  # fmt: skip
    return "\n".join(out).rstrip() + "\n"


def comparison_markdown(prisma: dict[str, Any], whisper: dict[str, Any], source: str) -> str:
    """CER by condition: Prisma baseline and full fix vs the open model, same audio and normalisation."""
    settings = prisma["run"].get("settings") or ["F0", "F3"]
    base, fixed = ("F0" if "F0" in settings else settings[0]), ("F3" if "F3" in settings else settings[-1])
    w_model = next((r["model"] for r in whisper["overall"]), "whisper")
    lines = [
        f"| Condition | n | Prisma {base} | Prisma {fixed} | {w_model} |",
        "|---|---|---|---|---|",
    ]
    for c in CONDITIONS:
        p0 = next((r for r in prisma["overall"] if r["source"] == source and r["condition"] == c and r["setting"] == base), None)
        p3 = next((r for r in prisma["overall"] if r["source"] == source and r["condition"] == c and r["setting"] == fixed), None)
        w = next((r for r in whisper["overall"] if r["source"] == source and r["condition"] == c), None)
        if not (p0 or p3 or w):
            continue
        n = _n_label([x["n"] for x in (p0, p3, w) if x])
        cells = [pct(x.get("cer")) if x else "–" for x in (p0, p3, w)]
        lines.append(f"| {c} {CONDITIONS[c].label} | {n} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def readme_results_block(prisma_run_name: str, prisma: dict[str, Any],
                         whisper: dict[str, Any] | None = None) -> str:  # fmt: skip
    """The README 'Results' section, regenerated by scripts/make_report.py."""
    run = prisma["run"]
    out = [
        f"Generated from [`results/{prisma_run_name}/summary.json`](results/{prisma_run_name}/summary.json) "
        f"on {run.get('created_at', '')[:10]} ({run.get('split')} split). "
        "CER/WER in % with bootstrap 95% CI; n = utterances.",
        "",
        f"![KuralCheck scorecard](results/{prisma_run_name}/scorecard.png)",
        "",
        summary_markdown(prisma, headline_only=True).strip(),
    ]
    if whisper:
        for source in ("real", "timbre"):
            if any(r["source"] == source for r in whisper["overall"]):
                out += ["", f"**Open-model comparison · {SOURCE_LABELS[source]} · CER %**", "",
                        comparison_markdown(prisma, whisper, source)]  # fmt: skip
    out += ["", f"Full tables: [`results/{prisma_run_name}/tables.md`](results/{prisma_run_name}/tables.md) · "
            f"error list: [`errors.md`](results/{prisma_run_name}/errors.md)"]  # fmt: skip
    return "\n".join(out)


README_START = "<!-- results:start -->"
README_END = "<!-- results:end -->"


def replace_readme_block(readme: str, block: str) -> str:
    if README_START not in readme or README_END not in readme:
        raise ValueError("README.md is missing the results markers")
    head, rest = readme.split(README_START, 1)
    _, tail = rest.split(README_END, 1)
    return f"{head}{README_START}\n{block}\n{README_END}{tail}"
