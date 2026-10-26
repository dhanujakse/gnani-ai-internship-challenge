# KuralCheck Chrome extension

A developer tool for testing how Gnani Prisma hears Tamil, from inside the browser.

| Where | What |
|---|---|
| Toolbar popup | Quick one-sentence test: clean vs noisy phone line, raw (F0) vs fix layer (F3) |
| Right-click selected text | "Test with KuralCheck" — sends the selected Tamil sentences to the tester |
| Full tester page | Test text (≤ 10 sentences) · Test voice (record or upload) · Score a transcript · Fix a transcript · Benchmark results · Settings |
| DevTools panel | The same tester as a "KuralCheck" tab in Chrome DevTools |

The extension holds **no API key**. It talks to the KuralCheck server, which keeps the Gnani key,
caches every call, paces calls adaptively and caps daily use.

## Install (2 minutes)

1. Start the server in the project folder (needs `GNANI_API_KEY` in `.env`):
   ```bash
   uv run uvicorn kuralcheck.api:app --port 8765
   ```
2. Chrome → `chrome://extensions` → turn on **Developer mode** → **Load unpacked** → choose this
   `extension/` folder (or unzip `dist/kuralcheck-extension-v1.0.0.zip` and choose that folder).
3. Pin **KuralCheck** in the toolbar. The pill at the top right says "server ok" when it is connected.

Using a hosted server instead? Open **Settings**, enter its `https://` URL (Chrome asks for permission)
and the token if the server sets `KURALCHECK_API_TOKEN`.

## Cost per action

| Action | Gnani calls |
|---|---|
| Score a transcript, Fix a transcript, Benchmark | 0 |
| Test text | up to 5 per new sentence (1 Timbre + 4 Prisma); repeats and duplicates are free (cached) |
| Test voice | 4 Prisma calls (recordings are never cached or stored) |

## Privacy

Recordings go only to your KuralCheck server and Gnani, are processed in a temporary folder and deleted.
The microphone works in the full tester tab; Chrome does not allow it inside the DevTools panel.
