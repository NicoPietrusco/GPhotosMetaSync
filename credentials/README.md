# OAuth credentials (one-time setup for whoever packages the app)

This project runs as a **local app** on one computer. **End users** only need a Google account to sign in; they do **not** need a Google Cloud project.

Someone who **builds or distributes** the app must create OAuth credentials **once** in [Google Cloud Console](https://console.cloud.google.com/) and ship the client JSON with the app (or place it in `credentials/`).

## Steps

1. Open Google Cloud Console and select or create a **project**.
2. **APIs & Services** → **Library** → enable **Google Photos Picker API**.
3. **OAuth consent screen** — configure if prompted (External + test users while in Testing).
4. **APIs & Services** → **Credentials** → **Create credentials** → **OAuth client ID**.
5. Application type: **Desktop app** (Installed).
6. Create, then **Download JSON**.
7. Save as **`credentials/client_secrets.json`** in this repo, **or** set `GOOGLE_OAUTH_CLIENT_SECRETS` to the full path.

Run `just verify` to confirm the JSON is in place and the app loads, then start the app (`just web`), open `http://127.0.0.1:5001` (default port; use 5001 on macOS to avoid AirPlay using 5000), and click **Sign In**. A browser window completes OAuth; tokens are stored locally as `credentials/google_token.json` (gitignored).

## Security

Do **not** commit `client_secrets.json`, `google_token.json`, or `token_*.pickle`. They are listed in `.gitignore`.
