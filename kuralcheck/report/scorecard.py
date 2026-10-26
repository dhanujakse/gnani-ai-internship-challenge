"""1200x1200 scorecard PNG + the JSON of exactly the numbers it shows.

Everything is read from summary.json (and optionally a Whisper summary.json); nothing is typed in.
Headline = real recordings when present, otherwise synthetic. Fonts: Noto Sans + Noto Sans Tamil.
"""

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from kuralcheck.audio.conditions import CONDITIONS  # noqa: E402
from kuralcheck.data import ROOT  # noqa: E402
from kuralcheck.report.tables import CATEGORY_LABELS, SOURCE_LABELS  # noqa: E402

FONT_DIR = ROOT / "assets" / "fonts"
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
SERIES = {"baseline": "#2a78d6", "fixed": "#eb6834", "whisper": "#1baf7a"}  # validated, fixed order

_fonts_ready = False


def _setup_fonts() -> None:
    global _fonts_ready
    if _fonts_ready:
        return
    for f in FONT_DIR.glob("*.ttf"):
        font_manager.fontManager.addfont(str(f))
    # per-glyph fallback: Latin -> Tamil -> symbols such as → (DejaVu ships with matplotlib)
    plt.rcParams["font.family"] = ["Noto Sans", "Noto Sans Tamil", "DejaVu Sans"]
    _fonts_ready = True


def _row(rows: list[dict], **match: str) -> dict | None:
    for r in rows:
        if all(r.get(k) == v for k, v in match.items()):
            return r
    return None


def _ci(row: dict | None, metric: str = "cer") -> dict | None:
    if not row or not row.get(metric) or row[metric]["value"] != row[metric]["value"]:
        return None
    return row[metric]


def scorecard_data(summary: dict[str, Any], whisper: dict[str, Any] | None = None) -> dict[str, Any]:
    run = summary["run"]
    overall = summary["overall"]
    model = next((r["model"] for r in overall), "")
    sources = {r["source"] for r in overall}
    headline = "real" if "real" in sources else "timbre"
    settings = run.get("settings") or sorted({r["setting"] for r in overall})
    base = "F0" if "F0" in settings else settings[0]
    fixed = "F3" if "F3" in settings else settings[-1]
    conds = [c for c in CONDITIONS if any(r["condition"] == c for r in overall)]
    worst_cond = conds[-1] if conds else None

    by_cond = []
    for c in conds:
        b = _ci(_row(overall, source=headline, condition=c, setting=base))
        f = _ci(_row(overall, source=headline, condition=c, setting=fixed))
        entry: dict[str, Any] = {"condition": c, "label": CONDITIONS[c].label, "baseline": b, "fixed": f}
        if whisper:
            entry["whisper"] = _ci(_row(whisper["overall"], source=headline, condition=c))
        by_cond.append(entry)

    cats = []
    for r in summary["by_category"]:
        if r["condition"] == worst_cond and r["setting"] == base and _ci(r):
            cats.append({"source": r["source"], "category": r["category"], "cer": r["cer"], "n": r["n"]})
    cats.sort(key=lambda x: x["cer"]["value"], reverse=True)

    numbers = {}
    for setting in (base, fixed):
        row = _row(overall, source="timbre", condition=worst_cond, setting=setting) if worst_cond else None
        numbers[setting] = _ci(row, "number_accuracy")

    gain = None
    if by_cond and by_cond[-1]["baseline"] and by_cond[-1]["fixed"]:
        gain = round(100 * (by_cond[-1]["baseline"]["value"] - by_cond[-1]["fixed"]["value"]), 1)

    n_by_source = {}
    for s in sorted(sources):
        row = _row(overall, source=s, condition=conds[0], setting=base) if conds else None
        n_by_source[s] = row["n"] if row else 0

    return {
        "model": model,
        "split": run.get("split"),
        "date": (run.get("created_at") or "")[:10],
        "git_commit": run.get("git_commit"),
        "models": run.get("models", {}),
        "headline_source": headline,
        "n_by_source": n_by_source,
        "settings": {"baseline": base, "fixed": fixed},
        "cer_by_condition": by_cond,
        "worst_condition": worst_cond,
        "worst_categories": cats[:6],
        "fix_gain_points_worst_condition": gain,
        "number_accuracy_worst_condition": numbers,
        "latency_ms": run.get("latency_ms"),
        "prisma_calls": run.get("prisma_calls"),
        "whisper_model": next((r["model"] for r in whisper["overall"]), None) if whisper else None,
    }


def _pct(ci: dict | None) -> str:
    return "–" if not ci else f"{100 * ci['value']:.1f}%"


def render_scorecard(data: dict[str, Any], out_png: Path) -> None:
    _setup_fonts()
    fig = plt.figure(figsize=(12, 12), dpi=100, facecolor=SURFACE)
    split = data["split"] or ""
    n_txt = " · ".join(f"{s} n={n}" for s, n in data["n_by_source"].items())

    fig.text(0.06, 0.955, "KuralCheck", fontsize=34, weight="bold", color=TEXT)
    fig.text(0.06, 0.918, "குரல்செக் · How well does Gnani Prisma understand the Tamil people speak?",
             fontsize=16, color=TEXT_2)  # fmt: skip
    fig.text(0.06, 0.89, f"{SOURCE_LABELS[data['headline_source']]} · {split} split · {n_txt}",
             fontsize=13, color=TEXT_2)  # fmt: skip

    # --- Panel A: CER by condition, baseline vs full fix (vs Whisper)
    ax = fig.add_axes([0.08, 0.50, 0.88, 0.33], facecolor=SURFACE)
    series = [("baseline", f"Prisma {data['settings']['baseline']} baseline"),
              ("fixed", f"Prisma {data['settings']['fixed']} full fix")]  # fmt: skip
    if data.get("whisper_model"):
        series.append(("whisper", f"{data['whisper_model']} (open model)"))
    rows = data["cer_by_condition"]
    width = 0.8 / len(series)
    ymax = max([e[k]["high"] for e in rows for k, _ in series if e.get(k)] + [0.05]) * 100 * 1.25
    for i, (key, label) in enumerate(series):
        xs, ys, lo, hi = [], [], [], []
        for j, e in enumerate(rows):
            ci = e.get(key)
            if ci:
                xs.append(j + (i - (len(series) - 1) / 2) * width)
                ys.append(100 * ci["value"])
                lo.append(100 * (ci["value"] - ci["low"]))
                hi.append(100 * (ci["high"] - ci["value"]))
        ax.bar(xs, ys, width=width, color=SERIES[key], edgecolor=SURFACE, linewidth=2, label=label, zorder=3)
        ax.errorbar(xs, ys, yerr=[lo, hi], fmt="none", ecolor=TEXT_2, elinewidth=1.2, capsize=4, zorder=4)
        for x, y, h in zip(xs, ys, hi, strict=True):
            ax.text(x, y + h + ymax * 0.015, f"{y:.1f}", ha="center", va="bottom", fontsize=11, color=TEXT)
    ax.set_xticks(range(len(rows)), [f"{e['condition']}\n{e['label']}" for e in rows], fontsize=12, color=TEXT)
    ax.set_ylim(0, ymax)
    ax.set_ylabel("Character error rate, % (lower is better)", fontsize=12, color=TEXT_2)
    ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.tick_params(axis="y", colors=TEXT_2, labelsize=11)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.legend(loc="upper left", frameon=False, fontsize=12, ncol=len(series), labelcolor=TEXT)
    ax.set_title("Error rate by phone-line condition · bars show bootstrap 95% CI", loc="left",
                 fontsize=14, color=TEXT, pad=12)  # fmt: skip

    # --- Panel B: where it breaks (categories at the worst condition, baseline)
    cats = data["worst_categories"]
    bx = fig.add_axes([0.30, 0.13, 0.30, 0.27], facecolor=SURFACE)
    if cats:
        labels = [f"{CATEGORY_LABELS.get(c['category'], c['category'])} (n={c['n']})" for c in cats][::-1]
        vals = [100 * c["cer"]["value"] for c in cats][::-1]
        bx.barh(range(len(vals)), vals, color=SERIES["baseline"], edgecolor=SURFACE, linewidth=2, height=0.7)
        for y, v in enumerate(vals):
            bx.text(v + max(vals) * 0.02, y, f"{v:.1f}%", va="center", fontsize=11, color=TEXT)
        bx.set_yticks(range(len(vals)), labels, fontsize=11, color=TEXT)
        bx.set_xlim(0, max(vals) * 1.25 if max(vals) > 0 else 1)
    bx.set_xticks([])
    for side in ("top", "right", "bottom"):
        bx.spines[side].set_visible(False)
    bx.spines["left"].set_color(GRID)
    fig.text(0.06, 0.425, f"Where it breaks · CER by category at {data['worst_condition']}, baseline",
             fontsize=14, color=TEXT)  # fmt: skip

    # --- Panel C: stat tiles
    tiles = []
    base, fixed = data["settings"]["baseline"], data["settings"]["fixed"]
    gain = data["fix_gain_points_worst_condition"]
    if gain is not None:
        direction = "lower" if gain >= 0 else "higher"
        tiles.append((f"{abs(gain):.1f} pts {direction}", f"CER with the fix layer at {data['worst_condition']} ({base} → {fixed})"))
    na = data["number_accuracy_worst_condition"]
    if na.get(base) or na.get(fixed):
        tiles.append((f"{_pct(na.get(base))} → {_pct(na.get(fixed))}",
                      f"Numbers recovered at {data['worst_condition']} ({base} → {fixed})"))  # fmt: skip
    lat = data.get("latency_ms") or {}
    if lat.get("p50") is not None:
        tiles.append((f"{lat['p50'] / 1000:.2f} s / {lat['p95'] / 1000:.2f} s", f"Prisma latency p50 / p95 (n={lat['n']} calls)"))
    y = 0.36
    for value, label in tiles[:3]:
        fig.text(0.66, y, value, fontsize=24, weight="bold", color=TEXT)
        fig.text(0.66, y - 0.03, label, fontsize=11, color=TEXT_2)
        y -= 0.095

    models = data.get("models") or {}
    fig.text(0.06, 0.045,
             f"{data['date']} · STT: {models.get('stt_version', models.get('stt', ''))} · test audio TTS: {models.get('tts', '')} · "
             f"commit {data.get('git_commit')} · small team-made set, read the intervals",
             fontsize=10.5, color=TEXT_2)  # fmt: skip
    fig.text(0.06, 0.022, "Conditions: C1 clean 16 kHz · C2 300–3400 Hz at 8 kHz · C3/C4 noise at 15/5 dB SNR + G.711 μ-law",
             fontsize=10.5, color=TEXT_2)  # fmt: skip
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=100, facecolor=SURFACE)
    plt.close(fig)


def make_scorecard(summary_path: Path, out_dir: Path | None = None, whisper_summary: Path | None = None) -> dict:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    whisper = json.loads(whisper_summary.read_text(encoding="utf-8")) if whisper_summary else None
    out_dir = out_dir or summary_path.parent
    data = scorecard_data(summary, whisper)
    (out_dir / "scorecard.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    render_scorecard(data, out_dir / "scorecard.png")
    return data
