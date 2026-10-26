"""Zip the Chrome extension for sharing or the Chrome Web Store: dist/kuralcheck-extension-v<version>.zip

    uv run python scripts/package_extension.py
"""

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extension"
REQUIRED = ["manifest.json", "background.js", "api.js", "app.html", "app.js", "app.css",
            "popup.html", "popup.js", "devtools.html", "devtools.js"]  # fmt: skip


def main() -> int:
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    missing = [f for f in REQUIRED if not (EXT / f).exists()]
    missing += [p for p in manifest["icons"].values() if not (EXT / p).exists()]
    if missing:
        print(f"Missing files: {missing}")
        return 1
    out = ROOT / "dist" / f"kuralcheck-extension-v{manifest['version']}.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(EXT.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                z.write(f, f.relative_to(EXT).as_posix())
    print(f"Wrote {out.relative_to(ROOT).as_posix()} ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
