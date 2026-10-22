# Multi-Method Authentication API

Backend-only learning project using FastAPI, SQLAlchemy 2, PostgreSQL, JWT, Twilio Verify, Google OIDC, and GitHub OAuth.

## 1. Requirements

- Python 3.12+
- `uv`
- PostgreSQL running locally
- Twilio Verify service
- Google OAuth web client
- GitHub OAuth App

## 2. Create PostgreSQL database

In `psql` or pgAdmin, create a database:

```sql
CREATE DATABASE multi_auth_db;
```

Set `DATABASE_URL` in `.env` to match your local PostgreSQL username, password, host, port, and database. URL-encode special characters in the password if necessary.

## 3. Create environment and install packages (Windows PowerShell)

```powershell
uv sync
Copy-Item .env.example .env
```

Edit `.env` and replace the example values. Do not commit `.env`.

Generate strong secrets with Python:

```powershell
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use one generated value for `JWT_SECRET_KEY` and the other for `SESSION_SECRET_KEY`.

## 4. Configure Twilio Verify

1. Create/sign in to a Twilio account.
2. Create a Verify service and enable SMS.
3. Copy Account SID, Auth Token, and Verify Service SID into `.env`.
4. Send phone numbers in E.164 format, such as `+919876543210`.
5. Trial accounts may require destination numbers to be verified first.

## 5. Configure Google OIDC

1. Open https://console.cloud.google.com/.
2. Configure the OAuth consent screen and create an OAuth client ID for a Web application.
3. Add this authorized redirect URI exactly:
   `http://127.0.0.1:8000/auth/google/callback`
4. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`.

## 6. Configure GitHub OAuth

1. Open https://github.com/settings/developers and create a new OAuth App.
2. Homepage URL: `http://127.0.0.1:8000`
3. Authorization callback URL:
   `http://127.0.0.1:8000/auth/github/callback`
4. Set `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` in `.env`.

OAuth providers may reject callback URLs that differ from the registered URL. Use one hostname consistently (`127.0.0.1` versus `localhost`).

## 7. Run

```powershell
uv run uvicorn main:app --reload
```

Open:
- Swagger: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

On first startup, SQLAlchemy creates the tables automatically. This is convenient for learning; use Alembic migrations for a production app.

## 8. Test OTP

In Swagger:
1. `POST /auth/otp/send`
2. Body:
   ```json
   {"phone_number":"+919876543210"}
   ```
3. Enter the received code into `POST /auth/otp/verify`:
   ```json
   {"phone_number":"+919876543210","code":"123456"}
   ```
4. Copy `access_token` from the response.
5. Click **Authorize** in Swagger and enter `Bearer YOUR_TOKEN` if prompted. Then call `GET /auth/me`.

If Twilio is not configured, OTP endpoints return HTTP 503 instead of pretending to send a code.

## 9. Test Google and GitHub

Open these URLs in a browser (not Swagger's Try it out):
- http://127.0.0.1:8000/auth/google/login
- http://127.0.0.1:8000/auth/github/login

Complete the provider sign-in. The callback returns the application JWT in a JSON response. This is useful for local backend testing only. For production browser clients, do not expose access tokens in a page or URL; redirect to the frontend using a short-lived, single-use handoff code or use a secure cookie-based session architecture.

## 10. Endpoint summary

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/auth/otp/send` | Send SMS verification |
| POST | `/auth/otp/verify` | Verify code and issue JWT |
| GET | `/auth/me` | Get current user; bearer token required |
| POST | `/auth/logout` | Client-side logout guidance |
| GET | `/auth/google/login` | Begin Google OIDC |
| GET | `/auth/google/callback` | Google callback |
| GET | `/auth/github/login` | Begin GitHub OAuth |
| GET | `/auth/github/callback` | GitHub callback |

## Security notes / limitations

- JWT access tokens expire after 15 minutes by default. The sample intentionally does not implement refresh tokens.
- `/auth/logout` cannot invalidate a stateless JWT. Client must discard it. Implement server-side revocation or refresh-token sessions if immediate revocation is required.
- Add rate limiting (for example, Redis-backed limits) to OTP endpoints and OAuth initiation in production.
- Use HTTPS in production and set `COOKIE_SECURE=true`.
- Keep secrets out of source control and logs.
- Do not auto-link accounts by email alone. This sample keys linked OAuth identities by provider and stable provider user ID.
- For Google, Authlib uses the provider's OIDC discovery metadata and parses the ID token/userinfo when configured with the `openid` scope. Review and test this behavior against your Authlib version before production deployment.
- Use Alembic migrations instead of `create_all` once schema changes need to be managed.
- The callback's JSON response contains an access token for local backend testing. For production browser apps, use a secure frontend handoff/session design instead.
