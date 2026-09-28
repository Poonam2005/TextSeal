# TextSeal

TextSeal is a final-year BE Django project for watermarking text and verifying its provenance and integrity. It implements the core PRD flow:

1. Canonicalize input text.
2. Generate a unique text ID and signed invisible watermark.
3. Embed the watermark using zero-width Unicode characters.
4. Store the SHA-256 hash and provenance record in SQLite.
5. Append a tamper-evident local ledger block.
6. Extract the watermark and compare the submitted hash, record, and ledger state.

Read [the final-year project guide](docs/FINAL_YEAR_PROJECT_GUIDE.md) before preparing your report or review, and use [the demo and viva guide](docs/DEMO_AND_VIVA_GUIDE.md) for presentation practice.

## Run locally

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000`.

## Security configuration

Set `TEXTSEAL_SECRET_KEY` and `TEXTSEAL_WATERMARK_SECRET` in the environment before deployment; see `.env.example` for the required values. The development defaults are intentionally unsuitable for production. The default implementation is a clearly labelled local tamper-evident hash chain, not a public blockchain transaction. A real Ethereum/Polygon adapter can be added once the contract ABI and storage policy are agreed.

## Verification semantics

This prototype verifies an *exact canonical text representation*. An embedded zero-width watermark identifies a known registration; a changed canonical hash produces **Modified / tampered**. Zero-width watermarks are appropriate for an academic prototype but are not resilient to aggressive reformatting, copy/paste sanitization, or paraphrasing. Those conditions can remove the watermark and result in **Not registered** rather than a proof of authenticity.

## Test

```powershell
.\.venv\Scripts\python.exe manage.py test
```
