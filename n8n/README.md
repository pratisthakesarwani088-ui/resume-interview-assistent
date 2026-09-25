# n8n workflows

See the main [README.md](../README.md#n8n-workflow-orchestration) for the
full explanation of what n8n does (and deliberately does *not* do) in this
project. This folder just holds the workflow definition.

## Importing the workflow

1. Open n8n (local: http://localhost:5678, credentials from your `.env`;
   Render: the URL Render gives the `interview-assistant-n8n` service).
2. **Workflows → Import from File** → select `workflows/resume-analysis-pipeline.json`.
3. Set the `DJANGO_API_BASE_URL` environment variable on the n8n
   service/container (e.g. `http://backend:8000` in docker-compose,
   or the Django service's Render URL) — the workflow reads it via
   `{{ $env.DJANGO_API_BASE_URL }}`, it's not hardcoded in the JSON.
4. Activate the workflow. n8n will show the generated webhook URL.

## Triggering it

```bash
curl -X POST "http://localhost:5678/webhook/resume-analysis-pipeline" \
  -H "Content-Type: application/json" \
  -d '{"access_token": "<a valid Django JWT access token for that user>"}'
```

This calls Django's existing `POST /api/analysis/analyze/` as that user —
Django's own auth and ownership checks still apply, so this workflow can
never analyze or return another user's resume. It's an optional, external
way to trigger the same analysis the React app already triggers automatically
after upload — not a required part of the normal flow.
