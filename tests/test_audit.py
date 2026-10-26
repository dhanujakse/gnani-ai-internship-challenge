from pathlib import Path

import pytest

from kuralcheck import audit


def files(tmp_path: Path, contents: dict[str, str]) -> list[Path]:
    out = []
    for rel, text in contents.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        out.append(p)
    return out


def test_secret_scan_flags_keys_and_tracked_env(tmp_path) -> None:
    fs = files(tmp_path, {
        ".env": "GNANI_API_KEY=abc",
        "kuralcheck/x.py": 'API_KEY = "sk_live_1234567890abcdef"\n',
        ".env.example": "GNANI_API_KEY=\n",
        "tests/t.py": 'api_key="test-key-123456789"',
    })  # fmt: skip
    findings = audit.check_secrets(fs, tmp_path)
    assert any(".env is tracked" in f for f in findings)
    assert any("kuralcheck/x.py" in f for f in findings)
    assert not any(".env.example" in f or "tests/" in f for f in findings)


def test_secret_scan_ignores_settings_code(tmp_path) -> None:
    fs = files(tmp_path, {"kuralcheck/config.py": 'gnani_api_key: SecretStr = SecretStr("")\n'})
    assert audit.check_secrets(fs, tmp_path) == []


@pytest.mark.parametrize("text", ["call me on 98400 12345", "+91 9840012345", "aadhaar 1234 5678 9012", "a@b.com"])
def test_personal_data_patterns(tmp_path, text) -> None:
    fs = files(tmp_path, {"data/notes.csv": text})
    findings = [f for f in audit.check_personal_data(fs, tmp_path) if "data/notes.csv" in f]
    assert findings


def test_numbers_in_sentences_are_not_personal_data(tmp_path) -> None:
    fs = files(tmp_path, {"data/x.csv": "இருபத்தைந்து=25|1200|250000|12000"})
    assert [f for f in audit.check_personal_data(fs, tmp_path) if "data/x.csv" in f] == []


def test_split_leakage(tmp_path, monkeypatch) -> None:
    bias = tmp_path / "bias.txt"
    variants = tmp_path / "variants.csv"
    # "தொண்ணூற்றொன்பது" only appears in test sentence num08; "இருபத்தைந்து" is in dev sentence num01
    bias.write_text("தொண்ணூற்றொன்பது\nஇருபத்தைந்து\n", encoding="utf-8")
    variants.write_text("pattern,replacement,category\nதொண்ணுத்தொம்பது,தொண்ணூற்றொன்பது,numbers\n", encoding="utf-8")
    monkeypatch.setattr(audit, "BIAS_WORDS_TXT", bias)
    monkeypatch.setattr(audit, "VARIANTS_CSV", variants)
    findings = audit.check_split_leakage()
    assert len(findings) == 2 and all("தொண்ணூற்றொன்பது" in f for f in findings)


def test_repo_passes_static_checks() -> None:
    assert audit.check_secrets() == []
    assert audit.check_split_leakage() == []
    assert audit.check_readme_numbers() == []
