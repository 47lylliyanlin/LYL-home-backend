# Kiro Cloud Security and Backup Checklist

> Window C scope: Dashboard/API protection, secret hygiene, persistence, backup/restore, and health checks.

## 1. Admin Token

Set `KIRO_ADMIN_TOKEN` before exposing Dashboard or debug/admin APIs.

Protected paths:

- `/dashboard`
- `/api/gateway/*`
- `/api/profile/*`
- `/api/memory/*`
- `/api/darkroom/*`
- `/api/dream/*`
- `/api/maintenance/*`
- `/api/pulse`
- `/api/introspection`
- `/api/ai/config`

Use header:

```text
X-Kiro-Admin-Token: your_admin_token
```

Temporary browser debugging:

```text
https://your-domain/dashboard/?admin_token=your_admin_token
```

If `KIRO_ADMIN_TOKEN` is empty, protected routes stay open for local development.

## 2. CORS

Local development:

```env
KIRO_CORS_ORIGINS=*
```

Cloud deployment:

```env
KIRO_CORS_ORIGINS=https://your-frontend-domain
```

Use comma-separated values for multiple origins.

## 3. Never Commit

Do not commit these files or directories:

- `.env`
- `memory/`
- `runtime/`
- `chroma_db/`
- `*.log`
- `audio/input/*`
- `audio/output/*`

## 4. Persistent Data

Must persist:

- `memory/`
- `chroma_db/`

Recommended to persist:

- `runtime/sessions/`
- `runtime/recent_turns.jsonl`
- `runtime/last_injected_context.json`

Temporary/cache data:

- `audio/input/`
- `audio/output/`
- `*.log`

## 5. Manual Backup

From backend root:

```powershell
cd F:\kiro-project\backend
.\venv\Scripts\python.exe tools\backup_data.py
```

Default output:

```text
backups/kiro_backup_YYYYMMDD_HHMMSS.zip
```

The backup includes:

- `memory/`
- `runtime/`
- `chroma_db/`
- `backup_manifest.json`

The backup excludes:

- `.env`
- logs
- audio cache

Smaller backup without vector database:

```powershell
.\venv\Scripts\python.exe tools\backup_data.py --no-chroma
```

## 6. Restore

1. Stop backend.
2. Unzip archive into backend root.
3. Confirm these paths exist:

```text
backend/memory/
backend/runtime/
backend/chroma_db/
```

4. Restart backend.
5. Check these endpoints:

- `/`
- `/api/ai/config`
- `/api/pulse`
- `/api/gateway/last-context`

## 7. Pre-Cloud Checklist

- `.env` is not committed.
- `KIRO_ADMIN_TOKEN` is set.
- `KIRO_CORS_ORIGINS` is restricted in production.
- Dashboard requires token in production.
- `/api/ai/config` hides API keys.
- `memory/` and `chroma_db/` are persistent or backed up.
- `tools/backup_data.py` has been tested.
- Process manager or restart policy exists.
- Frontend uses HTTPS in production.
