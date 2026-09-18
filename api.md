# API Reference — Network Graph Intelligence Project

**This project does not use any external APIs or API keys.**

All data is generated locally (synthetic). All analysis runs locally (NetworkX, PyG). The dashboard runs locally (Plotly Dash). Explanations use built-in Python templates.

There is nothing to configure in `.env` for outbound HTTP calls.

---

## What runs locally

| Component | Technology | External network? |
|---|---|---|
| Data | SQLite + synthetic generator | No |
| Graph analysis | NetworkX | No |
| Predictions (Phase 2) | PyTorch Geometric | No |
| Dashboard | Plotly Dash on `DASH_HOST:DASH_PORT` | No (local browser only) |
| Explanations | Template strings in Python | No |

---

## Environment config (not an API)

Runtime settings live in `.env` — paths, seed, dashboard port. Validated by:

```bash
python scripts/check_env.py
```

See `.env.example` for the full list. No secrets required.

---

## If you ever extended this project

A future version might add real company data via HTTP. That is **out of scope** for the current build. This doc stays intentionally short because there are no API calls to document.
