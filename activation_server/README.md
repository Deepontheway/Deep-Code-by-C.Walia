# Deep Code Activation Server

Hosted approval server for Deep Code by C.Walia. The desktop app submits an activation request, the owner approves it in the dashboard, and the server returns a signed Ed25519 access code. The app verifies that code offline against the public key bundled with the app.

## What the server stores

- Install ID (`DC-XXXX-XXXX-XXXX`)
- Name, email, and note supplied by the user
- Request status, issued code, timestamps
- SQLite database at `ACTIVATION_DB`

The server never needs the user's API keys, chats, or files.

## Required secrets

| Variable | Purpose |
| --- | --- |
| `OWNER_TOKEN` | Long random password for the owner dashboard and admin API |
| `ACTIVATION_PRIVATE_KEY_PATH` | Path to the owner Ed25519 private key |
| `ACTIVATION_PRIVATE_KEY_PEM` | Alternative: PEM contents, with `\n` escapes |
| `ACTIVATION_DB` | SQLite database path, default `activation_server/data/activation.sqlite3` |

The private key must be the one matching `app/walia/activation_public_key.pem`. The existing owner key is stored outside the repo at `%LOCALAPPDATA%\Deep Code by C.Walia\owner_private_key.pem`. Never commit the private key, the owner token, or the database.

Generate a token:

```powershell
.\venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Run locally

From the repo root:

```powershell
$env:OWNER_TOKEN = "your-long-token"
$env:ACTIVATION_PRIVATE_KEY_PATH = "$env:LOCALAPPDATA\Deep Code by C.Walia\owner_private_key.pem"
$env:ACTIVATION_DB = "$env:TEMP\deepcode-activation.sqlite3"
.\venv\Scripts\python.exe -m uvicorn activation_server.app:app --host 127.0.0.1 --port 8800
```

Open <http://127.0.0.1:8800>, enter the owner token, and approve requests.

## Connect the desktop app

Add `activation_server` to `%LOCALAPPDATA%\Deep Code by C.Walia\config.json`:

```json
{
  "activation_server": "https://your-activation-host.example.com"
}
```

Or set the environment variable before launching the app:

```powershell
$env:WALIACODE_ACTIVATION_SERVER = "https://your-activation-host.example.com"
```

The URL must be HTTPS for anything other than localhost. The app falls back to email activation if the server is unreachable.

## Deploy

The server is a standard ASGI app with one dependency on `cryptography`.

### Docker host with a persistent volume

```powershell
docker build -f activation_server/Dockerfile -t deepcode-activation .
docker run -d --name deepcode-activation -p 8000:8000 `
  -e OWNER_TOKEN="your-long-token" `
  -e ACTIVATION_PRIVATE_KEY_PEM="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n" `
  -v deepcode-activation-data:/data `
  deepcode-activation
```

Put HTTPS in front with Caddy, Nginx, Cloudflare Tunnel, or your host's TLS.

### Free Render + Neon Postgres (recommended)

Render's free web service has an ephemeral filesystem, so use Neon's free Postgres instead of SQLite. The server automatically switches to Postgres when `DATABASE_URL` is set.

1. Create a free Postgres database at <https://neon.tech> and copy its connection string.
2. Push this repo to GitHub.
3. In Render, choose **New > Blueprint**, select the repo, and apply `render.yaml`.
4. Set these Render environment secrets:
   - `OWNER_TOKEN` - long random owner password
   - `ACTIVATION_PRIVATE_KEY_PEM` - contents of `owner_private_key.pem` (keep `\n` escapes)
   - `DATABASE_URL` - the Neon connection string (`postgresql://...?sslmode=require`)
5. Deploy and open `https://<service>.onrender.com/health`. It should report `"status":"ok"` and `"database":"postgres"`.
6. Put the service URL into the desktop config:

```json
{
  "activation_server": "https://<service>.onrender.com"
}
```

Render free services sleep after inactivity, so the first request can take ~30 seconds. Neon free Postgres keeps requests and approved codes across restarts.

If you prefer SQLite, run the server on a host with a persistent volume mounted at `/data` and set `ACTIVATION_DB=/data/activation.sqlite3`. Without a volume, requests disappear on redeploy.

## API

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/requests` | none | Create or reuse a pending request |
| `GET` | `/api/requests/{id}` | none | Check status; returns the code when approved |
| `GET` | `/api/admin/requests` | Bearer token | List requests |
| `GET` | `/api/admin/stats` | Bearer token | Counts by status |
| `POST` | `/api/admin/requests/{id}/approve` | Bearer token | Sign and attach a code |
| `POST` | `/api/admin/requests/{id}/reject` | Bearer token | Reject a request |
| `GET` | `/health` | none | Health check |

## Offline fallback

The owner tool still works without the server:

```powershell
.\venv\Scripts\python.exe scripts\activation_owner.py issue --install-id DC-XXXX-XXXX-XXXX --name "Name" --email "you@example.com" --days 365
```

Send that code to the user, and they paste it into the activation screen.
