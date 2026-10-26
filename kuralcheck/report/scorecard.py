"""1200x1200 scorecard PNG + the JSON of exactly the numbers it shows.

Everything is read from summary.json (and optionally a Whisper summary.json); nothing is typed in.
Headline = real recordings when present, otherwise synthetic. Fonts: Noto Sans + Noto Sans Tamil.

Panels: CER by condition for every Prisma setting (and Whisper) with 95% CI; where it breaks
(categories at the hardest condition); four tiles: cost of noise, what the fix layer recovers,
Prisma vs the open model (or numbers), and latency.
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
# validated categorical order (dataviz palette check); same colours as the app and extension
COLORS = {"F0": "#2a78d6", "F1": "#eda100", "F2": "#6250d6", "F3": "#eb6834", "W0": "#1baf7a"}
NAMES = {"F0": "F0 raw", "F1": "F1 ITN", "F2": "F2 ITN + hints", "F3": "F3 full fix", "W0": "Whisper small"}
SETTING_ORDER = ("F0", "F1", "F2", "F3")

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


def _val(ci: dict | None) -> float | None:
    return None if ci is None else ci["value"]


def scorecard_data(summary: dict[str, Any], whisper: dict[str, Any] | None = None) -> dict[str, Any]:
    run = summary["run"]
    overall = summary["overall"]
    sources = {r["source"] for r in overall}
    headline = "real" if "real" in sources else "timbre"
    present = {r["setting"] for r in overall}
    settings = [s for s in SETTING_ORDER if s in present] or sorted(present)
    conds = [c for c in CONDITIONS if any(r["condition"] == c for r in overall)]
    clean, worst = (conds[0], conds[-1]) if conds else (None, None)
    base = settings[0]

    by_cond = []
    for c in conds:
        entry: dict[str, Any] = {
            "condition": c,
            "label": CONDITIONS[c].label,
            "cer": {s: _ci(_row(overall, source=headline, condition=c, setting=s)) for s in settings},
        }
        if whisper:
            entry["cer"]["W0"] = _ci(_row(whisper["overall"], source=headline, condition=c))
        by_cond.append(entry)

    def cer_at(cond: str | None, setting: str) -> float | None:
        e = next((x for x in by_cond if x["condition"] == cond), None)
        return _val(e["cer"].get(setting)) if e else None

    # cost of noise: raw CER, clean vs hardest condition
    noise = None
    c0, cw = cer_at(clean, base), cer_at(worst, base)
    if c0 is not None and cw is not None and worst != clean:
        noise = {"setting": base, "clean": c0, "worst": cw, "points": round(100 * (cw - c0), 1),
                 "ratio": round(cw / c0, 1) if c0 > 0 else None}  # fmt: skip

    # fix layer: F3 vs the setting it post-processes (F2), and the share of ITN formatting loss recovered
    fix = None
    if "F3" in settings and "F2" in settings:
        f2, f3, f0 = cer_at(worst, "F2"), cer_at(worst, "F3"), cer_at(worst, "F0")
        if f2 is not None and f3 is not None:
            share = (f2 - f3) / (f2 - f0) if f0 is not None and f2 > f0 else None
            fix = {"condition": worst, "f2": f2, "f3": f3, "points": round(100 * (f2 - f3), 1),
                   "share_of_itn_loss_recovered": round(share, 2) if share is not None else None}  # fmt: skip

    best = min(((s, cer_at(worst, s)) for s in settings if cer_at(worst, s) is not None), key=lambda x: x[1], default=None)

    vs_open = None
    if whisper:
        w, p = cer_at(worst, "W0"), cer_at(worst, best[0] if best else base)
        if w is not None and p is not None:
            vs_open = {"condition": worst, "prisma_setting": best[0] if best else base, "prisma": p, "whisper": w}

    numbers = {s: _ci(_row(overall, source="timbre", condition=worst, setting=s), "number_accuracy") for s in settings}

    cats = []
    for r in summary["by_category"]:
        if r["condition"] == worst and r["setting"] == base and r["source"] == headline and _ci(r):
            cats.append({"category": r["category"], "cer": r["cer"], "n": r["n"]})
    cats.sort(key=lambda x: x["cer"]["value"], reverse=True)

    n_by_source = {}
    for s in sorted(sources):
        row = _row(overall, source=s, condition=clean, setting=base) if clean else None
        n_by_source[s] = row["n"] if row else 0

    return {
        "split": run.get("split"),
        "date": (run.get("created_at") or "")[:10],
        "git_commit": run.get("git_commit"),
        "models": run.get("models", {}),
        "headline_source": headline,
        "real_recordings_included": "real" in sources,
        "n_by_source": n_by_source,
        "settings": settings,
        "cer_by_condition": by_cond,
        "worst_condition": worst,
        "best_setting_worst_condition": best[0] if best else None,
        "noise_cost": noise,
        "fix_layer": fix,
        "vs_open_model": vs_open,
        "number_accuracy_worst_condition": numbers,
        "worst_categories": cats[:6],
        "latency_ms": run.get("latency_ms"),
        "prisma_calls": run.get("prisma_calls"),
        "whisper_model": next((r["model"] for r in whisper["overall"]), None) if whisper else None,
    }


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{100 * x:.1f}%"


def render_scorecard(data: dict[str, Any], out_png: Path) -> None:
    _setup_fonts()
    fig = plt.figure(figsize=(12, 12), dpi=100, facecolor=SURFACE)
    n_txt = " · ".join(f"{'real' if s == 'real' else 'synthetic'} n={n}" for s, n in data["n_by_source"].items())

    fig.text(0.06, 0.955, "KuralCheck", fontsize=34, weight="bold", color=TEXT)
    fig.text(0.06, 0.918, "குரல்செக் · How well does Gnani Prisma hear Tamil on a bad phone line?", fontsize=16, color=TEXT_2)
    sub = f"{SOURCE_LABELS[data['headline_source']]} · {data['split']} split · {n_txt}"
    if not data["real_recordings_included"]:
        sub += " · real recordings: coming next"
    fig.text(0.06, 0.89, sub, fontsize=12.5, color=TEXT_2)

    # --- Panel A: CER by condition for every setting (+ Whisper)
    ax = fig.add_axes((0.08, 0.50, 0.88, 0.33), facecolor=SURFACE)
    rows = data["cer_by_condition"]
    series = [s for s in (*data["settings"], "W0") if any(e["cer"].get(s) for e in rows)]
    width = 0.84 / max(1, len(series))
    tops = [e["cer"][s]["high"] for e in rows for s in series if e["cer"].get(s)]
    ymax = max(tops + [0.02]) * 100 * 1.22
    for i, s in enumerate(series):
        xs, ys, lo, hi = [], [], [], []
        for j, e in enumerate(rows):
            ci = e["cer"].get(s)
            if ci:
                xs.append(j + (i - (len(series) - 1) / 2) * width)
                ys.append(100 * ci["value"])
                lo.append(100 * (ci["value"] - ci["low"]))
                hi.append(100 * (ci["high"] - ci["value"]))
        ax.bar(xs, ys, width=width, color=COLORS.get(s, "#888"), edgecolor=SURFACE, linewidth=2, label=NAMES.get(s, s), zorder=3)
        ax.errorbar(xs, ys, yerr=[lo, hi], fmt="none", ecolor=TEXT_2, elinewidth=1, capsize=3, zorder=4)
        for x, y, h in zip(xs, ys, hi, strict=True):
            ax.text(x, y + h + ymax * 0.012, f"{y:.1f}", ha="center", va="bottom", fontsize=9.5, color=TEXT)
    ax.set_xticks(range(len(rows)), [f"{e['condition']}\n{e['label']}" for e in rows], fontsize=12, color=TEXT)
    ax.set_ylim(0, ymax)
    ax.set_ylabel("Character error rate, % (lower is better)", fontsize=12, color=TEXT_2)
    ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.tick_params(axis="y", colors=TEXT_2, labelsize=11)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.legend(loc="upper left", frameon=False, fontsize=11.5, ncol=len(series), labelcolor=TEXT)
    ax.set_title("Error rate by phone-line condition · whiskers: bootstrap 95% CI", loc="left", fontsize=14, color=TEXT, pad=12)

    # --- Panel B: where it breaks
    cats = data["worst_categories"]
    fig.text(0.06, 0.425, f"Where it breaks · CER by category at {data['worst_condition']} (raw)", fontsize=14, color=TEXT)
    bx = fig.add_axes((0.30, 0.13, 0.27, 0.27), facecolor=SURFACE)
    if cats:
        labels = [f"{CATEGORY_LABELS.get(c['category'], c['category'])} (n={c['n']})" for c in cats][::-1]
        vals = [100 * c["cer"]["value"] for c in cats][::-1]
        bx.barh(range(len(vals)), vals, color=COLORS["F0"], edgecolor=SURFACE, linewidth=2, height=0.7)
        for y, v in enumerate(vals):
            bx.text(v + max(vals + [0.1]) * 0.03, y, f"{v:.1f}%", va="center", fontsize=11, color=TEXT)
        bx.set_yticks(range(len(vals)), labels, fontsize=11, color=TEXT)
        bx.set_xlim(0, max(vals + [0.1]) * 1.3)
    bx.set_xticks([])
    for side in ("top", "right", "bottom"):
        bx.spines[side].set_visible(False)
    bx.spines["left"].set_color(GRID)

    # --- Panel C: tiles
    tiles: list[tuple[str, str]] = []
    nc = data.get("noise_cost")
    if nc:
        big = f"×{nc['ratio']}" if nc.get("ratio") else f"+{nc['points']} pts"
        tiles.append((big, f"Cost of noise: raw CER {_pct(nc['clean'])} clean → {_pct(nc['worst'])} at {data['worst_condition']}"))
    fx = data.get("fix_layer")
    if fx:
        share = fx.get("share_of_itn_loss_recovered")
        big = f"−{fx['points']:.1f} pts" if fx["points"] >= 0 else f"+{-fx['points']:.1f} pts"
        extra = f" ({round(100 * share)}% of ITN loss)" if share is not None else ""
        tiles.append((big, f"Fix layer at {fx['condition']}: F2 {_pct(fx['f2'])} → F3 {_pct(fx['f3'])}{extra}"))
    vo = data.get("vs_open_model")
    if vo:
        tiles.append((f"{_pct(vo['prisma'])} vs {_pct(vo['whisper'])}",
                      f"Prisma {vo['prisma_setting']} vs Whisper small at {vo['condition']} (CER)"))  # fmt: skip
    else:
        na = data["number_accuracy_worst_condition"]
        first = next((s for s in data["settings"] if na.get(s)), None)
        if first:
            tiles.append((_pct(na[first]["value"]), f"Numbers recovered at {data['worst_condition']} ({first}, n={na[first]['n']})"))
    lat = data.get("latency_ms") or {}
    if lat.get("p50") is not None:
        tiles.append((f"{lat['p50'] / 1000:.2f} s / {lat['p95'] / 1000:.2f} s", f"Prisma latency p50 / p95 (n={lat['n']} calls)"))
    y = 0.375
    for value, label in tiles[:4]:
        fig.text(0.62, y, value, fontsize=22, weight="bold", color=TEXT)
        fig.text(0.62, y - 0.026, label, fontsize=10.5, color=TEXT_2)
        y -= 0.082

    models = data.get("models") or {}
    fig.text(0.06, 0.045,
             f"{data['date']} · STT: {models.get('stt_version', models.get('stt', ''))} · test audio: Gnani Timbre {models.get('tts', '')} · "
             f"commit {data.get('git_commit')} · small team-made set: read the intervals",
             fontsize=10.5, color=TEXT_2)  # fmt: skip
    fig.text(0.06, 0.022, "C1 clean 16 kHz · C2 300–3400 Hz at 8 kHz · C3/C4 noise at 15/5 dB SNR + G.711 μ-law · "
             "F3 tuned on the dev split only", fontsize=10.5, color=TEXT_2)  # fmt: skip
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
