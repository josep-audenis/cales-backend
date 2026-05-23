# Cales Backend

FastAPI backend for procurement recommendations, website report JSON, executive PDF generation, and the UI-control agent.

## Local Run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

Copy `.env.example` to `.env` for local configuration.

## Key Endpoints

- `GET /health`
- `GET /commodities` and `GET /commodities/{material}`: frontend-compatible commodity data.
- `GET /signals`: frontend-compatible Intelligence feed data.
- `POST /agent/analyze`: website report JSON plus `executive_pdf`.
- `GET /agent/reports/{request_id}`: reload a stored generated report.
- `GET /reports/{request_id}/executive.pdf`: open the generated PDF.
- `POST /agent/ui`: screen-aware UI cursor actions.

## Configuration

- `PUBLIC_BASE_URL`: absolute backend URL used for PDF links.
- `CORS_ORIGINS`: comma-separated frontend origins, or `*` for demo mode.
- `REPORT_STORAGE_DIR`: filesystem directory for generated report JSON and PDF files.
- `HF_MODEL_BASE_URL`, `HF_MODEL_API_KEY`, `HF_MODEL_NAME`, `HF_MODEL_API_TYPE`: Hugging Face/OpenAI-compatible model endpoint aliases.

## Validation

```bash
python3 -m compileall -q app tests
.venv/bin/python -m pytest -q
```

Generated report/PDF bundles are written under `.cales_reports/`, which is ignored by git.
