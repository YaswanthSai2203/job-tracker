# Job Tracker

Flask app for tracking job applications and publishing a public job board.

## PostgreSQL (required for production)

**SQLite in `/tmp` (the default on Vercel without `DATABASE_URL`) does not keep your data.** Use a hosted PostgreSQL database so signups and logins survive deploys.

Pick one provider, create a database, then set **`DATABASE_URL`** in your host (Vercel, Render, etc.) to the connection string they give you.

### Neon (https://neon.tech)

1. Sign up and create a project.
2. In the dashboard, open your project → **Connection details**.
3. Copy the connection string. It often starts with `postgresql://` or `postgres://` (both work with this app).
4. Use the **pooled** or **direct** URI; enable SSL if Neon shows a `?sslmode=require` option (the app adds `sslmode=require` on Vercel/Render when missing).
5. In Vercel: **Project → Settings → Environment Variables** → add `DATABASE_URL` = paste the string → redeploy.

### Supabase (https://supabase.com)

1. Create a project → **Project Settings → Database**.
2. Under **Connection string**, choose **URI** and copy (role: `postgres` or the default they show).
3. Replace `[YOUR-PASSWORD]` with your database password if the UI shows a placeholder.
4. Set `DATABASE_URL` in Vercel/Render to that URI and redeploy.

### Vercel Postgres (https://vercel.com/docs/storage/vercel-postgres)

1. In the Vercel dashboard, open your project → **Storage** → create a Postgres store (or use the Vercel Postgres integration).
2. Link the database to the project; Vercel usually injects `POSTGRES_URL` or similar.
3. If the env name is not `DATABASE_URL`, either:
   - Map it in Vercel so **`DATABASE_URL`** equals the same value as `POSTGRES_URL`, or  
   - Add a `DATABASE_URL` variable manually from the connection string shown in the storage UI.

### After `DATABASE_URL` is set

1. **Redeploy** the app so it picks up the variable.
2. Run migrations once against that database (from your machine with the same URL, or a one-off command in CI):

   ```bash
   export DATABASE_URL="postgresql://..."
   pip install -r requirements.txt
   export FLASK_APP=app:create_app
   flask db upgrade
   ```

   If you rely on startup `create_all()` / `ensure_schema()` only, tables may still be created on first request, but **`flask db upgrade`** is the right way for Alembic revisions.

### Other important env vars

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Long random string; keeps sessions stable across deploys. |
| `DATABASE_URL` | PostgreSQL URI (see above). |
| `MAIL_SERVER`, `MAIL_PORT`, … | Optional SMTP for verification and password reset emails. |
| `ADMIN_EMAIL` | Who can access `/admin/jobs`. |

### Local PostgreSQL (optional)

If you want Postgres on your machine instead of SQLite:

```bash
docker compose up -d
export DATABASE_URL=postgresql://jobtracker:jobtracker@127.0.0.1:5432/jobtracker
export FLASK_APP=app:create_app
flask db upgrade
python app.py
```

Default credentials are in `docker-compose.yml` (dev only).

## Run locally (SQLite)

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5005
