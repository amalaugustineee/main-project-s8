# Medical Intelligence Frontend

A minimal static UI to interact with your FastAPI endpoints:

- Prescription: `POST /prescription` (file)
- Health Risk: `POST /healthrisk` (file)
- Diet Plan: `POST /generate-diet-plan` (file + region + condition + weight + age)

## Run backend

From the repo root:

```bash
uvicorn test.app:app --reload
```

The default base URL used by the UI is `http://127.0.0.1:8000`. You can change it at the top of the page and click Save.

## Open the frontend

Just open `frontend/index.html` in your browser. No build step is required.

If your browser blocks file:// fetch for CORS reasons, use a tiny static server, for example with Python:

```bash
# from repo root
python -m http.server 5500
# then open http://127.0.0.1:5500/frontend/index.html
```

## Notes

- Ensure your environment variables (`GEMINI_API_KEY`, optional `NCBI_API_KEY`, and `TESSERACT_CMD` on Windows if needed) are set for the backend.
- CORS is enabled for development (`*`). Tighten in production.

