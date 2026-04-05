# Google OAuth Setup

How to create the Google Cloud credentials needed for Gmail (and later Google Calendar).

---

## One-time setup

### 1. Create a Google Cloud project

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Click the project dropdown → **New Project**
3. Name it anything (e.g. "Personal Command Center") → **Create**
4. Make sure the new project is selected in the dropdown

### 2. Enable the Gmail API

1. Go to **APIs & Services → Library**
2. Search for **Gmail API** → click it → **Enable**
3. *(Later for Google Calendar: repeat with **Google Calendar API**)*

### 3. Configure the OAuth consent screen

1. Go to **APIs & Services → OAuth consent screen**
2. User type: **External** → **Create**
3. Fill in:
   - App name: `Personal Command Center` (or anything)
   - User support email: your Gmail address
   - Developer contact email: your Gmail address
4. Click **Save and Continue** through Scopes (no changes needed here)
5. On the **Test users** screen → **Add Users** → add your own Gmail address
6. Click **Save and Continue** → **Back to Dashboard**

> **Why test users?** While the app is in "testing" mode (unverified), only
> explicitly added test users can authorize it. For a personal tool this is fine
> and means you never need to go through Google's app verification process.

### 4. Create OAuth client credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Application type: **Web application**
4. Name: anything (e.g. "local dev")
5. Under **Authorized redirect URIs** → **Add URI**:
   ```
   http://localhost:8000/api/gmail/callback
   ```
6. Click **Create**
7. A dialog shows your **Client ID** and **Client Secret** — copy both

### 5. Add credentials to .env

In `apps/api/.env`:
```
GMAIL_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=your-client-secret-here
GMAIL_REDIRECT_URI=http://localhost:8000/api/gmail/callback
```

---

## What the scopes grant

| Scope | What it allows |
|---|---|
| `gmail.readonly` | Read Gmail messages and metadata — no send, no delete |
| `openid` | Confirm identity via Google Sign-In |
| `userinfo.email` | Read the account's email address |

---

## Connecting locally

Once credentials are in `.env` and the API server is running:

1. Open in your browser: `http://localhost:8000/api/gmail/auth`
2. You will be redirected to Google's consent screen
3. Log in with the Gmail account you added as a test user
4. Click **Allow**
5. You are redirected back to `http://localhost:8000/api/gmail/callback`
6. You should see a JSON response like:
   ```json
   {
     "status": "connected",
     "email": "you@gmail.com",
     "messages_total": 12345,
     "threads_total": 4321
   }
   ```

After this, tokens are stored at `apps/api/.tokens/gmail.json` (gitignored).

### Verify connection

```bash
curl http://localhost:8000/api/gmail/profile
```

Should return:
```json
{
  "email": "you@gmail.com",
  "messages_total": 12345,
  "threads_total": 4321
}
```

### Re-authenticate

Delete the token file and repeat the auth flow:
```bash
rm apps/api/.tokens/gmail.json
# Then open http://localhost:8000/api/gmail/auth in a browser
```

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `503 Gmail credentials are not configured` | `GMAIL_CLIENT_ID` or `GMAIL_CLIENT_SECRET` missing in `.env` | Add them and restart uvicorn |
| `redirect_uri_mismatch` from Google | The redirect URI in Google Cloud doesn't match | Make sure `http://localhost:8000/api/gmail/callback` is in Authorized redirect URIs |
| `access_denied` from Google | Your account isn't a test user | Add your email in OAuth consent screen → Test users |
| `401 Gmail not connected` from `/profile` | No token file yet | Complete the auth flow first |
