"""Pre-submission audit (build step 13): secrets, personal data, test-split leakage into the
fix layer, and README numbers that do not come from results/.
Each check returns a list of findings; an empty list means the check passed.
"""

import re
import subprocess
from pathlib import Path

from kuralcheck.data import REAL_AUDIO_DIR, ROOT, SENTENCES_CSV, load_sentences
from kuralcheck.fixlayer.bias import BIAS_WORDS_TXT, load_bias_words
from kuralcheck.fixlayer.lexicon import VARIANTS_CSV, load_lexicon
from kuralcheck.text.normalize import normalize
from kuralcheck.validate import validate

SECRET_FILES = (".env", ".streamlit/secrets.toml")
# KEY/TOKEN/SECRET/PASSWORD = "<long value>" in any tracked text file
SECRET_ASSIGN = re.compile(r"(?i)\b[\w-]*(api[_-]?key|token|secret|password|access[_-]?code)\b\s*[:=]\s*[\"']?([A-Za-z0-9_\-./+]{12,})")
PHONE_OR_ID = re.compile(r"(?<![\w.])(?:\+?91[ -]?)?[6-9]\d{4}[ -]?\d{5}(?!\d)|\b\d{4}[ -]\d{4}[ -]\d{4}\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
TEXT_SUFFIXES = {".py", ".md", ".csv", ".txt", ".toml", ".json", ".jsonl", ".yml", ".yaml", ".example", ""}
SKIP_DIRS = ("legacy/", "docs/", "assets/licenses/", "uv.lock", "requirements.txt")


def tracked_files(root: Path = ROOT) -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, encoding="utf-8")
    return [root / line for line in out.stdout.splitlines() if line]


def _text_files(files: list[Path], root: Path) -> list[tuple[str, str]]:
    result = []
    for f in files:
        rel = f.relative_to(root).as_posix()
        if rel.startswith(SKIP_DIRS) or f.suffix.lower() not in TEXT_SUFFIXES or not f.is_file():
            continue
        try:
            result.append((rel, f.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            continue
    return result


def check_secrets(files: list[Path] | None = None, root: Path = ROOT) -> list[str]:
    files = tracked_files(root) if files is None else files
    findings = []
    rels = {f.relative_to(root).as_posix() for f in files}
    for s in SECRET_FILES:
        if s in rels:
            findings.append(f"{s} is tracked by git: remove it (git rm --cached {s}) and rotate the key")
    for rel, text in _text_files(files, root):
        if rel.startswith("tests/"):
            continue  # tests use dummy keys like "test-key"
        for m in SECRET_ASSIGN.finditer(text):
            findings.append(f"{rel}: possible secret in '{m.group(0)[:40]}…'")
    return findings


def check_personal_data(files: list[Path] | None = None, root: Path = ROOT) -> list[str]:
    files = tracked_files(root) if files is None else files
    findings = [f"data validation: {e}" for e in validate(check_targets=False).errors]
    for rel, text in _text_files(files, root):
        if not (rel.startswith("data/") or rel.startswith("results/")):
            continue
        for m in PHONE_OR_ID.finditer(text):
            findings.append(f"{rel}: looks like a phone number or ID: {m.group(0)}")
        for m in EMAIL.finditer(text):
            findings.append(f"{rel}: email address: {m.group(0)}")
    allowed = {"README.md", "consent.csv"} | {f"{s.id}.wav" for s in load_sentences(SENTENCES_CSV) if s.source == "real"}
    for p in REAL_AUDIO_DIR.glob("*"):
        if p.name not in allowed and not p.name.startswith("."):
            findings.append(f"data/real/{p.name} is not listed in sentences.csv: remove or add it")
    return findings


def check_split_leakage() -> list[str]:
    """Fix-layer entries that only make sense for test-split sentences suggest tuning on test."""
    sents = load_sentences(SENTENCES_CSV)
    dev_words = {w for s in sents if s.split == "dev" for w in normalize(s.text).split()}
    test_words = {w for s in sents if s.split == "test" for w in normalize(s.text).split()} - dev_words
    findings = []
    for w in load_bias_words(BIAS_WORDS_TXT):
        if normalize(w) in test_words:
            findings.append(f"bias_words.txt: '{w}' appears only in test-split sentences (tune on dev only)")
    for rule in load_lexicon(VARIANTS_CSV).rules:
        target = normalize(rule.replacement)
        if target and all(t in test_words for t in target.split()):
            findings.append(f"variants.csv: '{rule.pattern}' -> '{rule.replacement}' only fixes test-split words")
    return findings


def check_readme_numbers(readme: Path = ROOT / "README.md") -> list[str]:
    """README results block must equal what make_report.py generates from the latest test run."""
    from kuralcheck.report.runs import latest
    from kuralcheck.report.tables import README_END, README_START, readme_results_block

    text = readme.read_text(encoding="utf-8")
    if README_START not in text:
        return ["README.md has no results markers"]
    current = text.split(README_START, 1)[1].split(README_END, 1)[0].strip()
    run = latest("test")
    if run is None:
        return [] if "No results yet" in current else ["README shows results but results/ has no test run"]
    whisper = latest("test", whisper=True)
    expected = readme_results_block(run.name, run.summary, whisper.summary if whisper else None).strip()
    if current != expected:
        return ["README results section is stale or hand-edited: run scripts/make_report.py"]
    return []


def run_all() -> dict[str, list[str]]:
    return {
        "No secrets in the repo": check_secrets(),
        "No personal data in data/ or results/": check_personal_data(),
        "Fix layer not tuned on the test split": check_split_leakage(),
        "README numbers generated from results/": check_readme_numbers(),
    }
