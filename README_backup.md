# Student Authentication API

A learning starter project using FastAPI, PostgreSQL, Twilio Verify OTP, Google OAuth, GitHub OAuth, and JWT access/refresh tokens.

## Folder structure

```text
student_auth/
├── .env                       # Create locally; never commit
├── .env.example
├── .gitignore
├── requirements.txt
├── check_db.py
├── README.md
└── app/
    ├── __init__.py
    ├── main.py
    ├── core/
    │   ├── __init__.py
    │   ├── config.py
    │   └── security.py
    ├── database/
    │   ├── __init__.py
    │   └── session.py
    ├── models/
    │   ├── __init__.py
    │   ├── user.py
    │   └── oauth_account.py
    ├── schemas/
    │   ├── __init__.py
    │   └── auth.py
    ├── routers/
    │   ├── __init__.py
    │   ├── otp.py
    │   ├── google.py
    │   ├── github.py
    │   ├── tokens.py
    │   └── users.py
    ├── services/
    │   ├── __init__.py
    │   └── token_service.py
    └── dependencies/
        ├── __init__.py
        └── current_user.py
```

## 1. Set up

Use Python 3.11+ recommended. Open a terminal in the `student_auth` project folder:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`:
- Put your actual PostgreSQL password in `DATABASE_URL`.
- Generate a strong JWT secret with `python -c "import secrets; print(secrets.token_hex(32))"`.
- Generate a different `SESSION_SECRET_KEY` the same way.
- Leave provider credentials blank until you configure each provider.

Create the PostgreSQL database once, using pgAdmin Query Tool connected to a different database such as `postgres`:

```sql
CREATE DATABASE student_auth_db;
```

Then check the connection:

```powershell
python check_db.py
```

Expected: `Database connection successful: 1`.

## 2. Run the API

```powershell
python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs.

## 3. Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Health check |
| POST | `/auth/otp/send` | Send OTP through Twilio Verify |
| POST | `/auth/otp/verify` | Verify OTP; create/find user and issue JWTs |
| GET | `/auth/google/login` | Begin Google OAuth |
| GET | `/auth/google/callback` | Google OAuth callback |
| GET | `/auth/github/login` | Begin GitHub OAuth |
| GET | `/auth/github/callback` | GitHub OAuth callback |
| POST | `/auth/refresh` | Exchange a refresh token for a new token pair |
| GET | `/users/me` | Get the current authenticated user's profile |

## 4. Configure Twilio Verify

Create a Twilio account and a Verify Service. Add the account SID, auth token, and Verify Service SID to `.env`, then restart the API. Phone numbers should be supplied in international format, e.g. `+919876543210`. Trial accounts may restrict which numbers can be messaged.

## 5. Configure Google OAuth

Create OAuth credentials in Google Cloud Console. Add this exact authorized redirect URI:

`http://localhost:8000/auth/google/callback`

Put the client ID and secret in `.env`, then restart the API. Visit `/auth/google/login` in a browser.

## 6. Configure GitHub OAuth

Create an OAuth App in GitHub Developer Settings. Set the Authorization callback URL to:

`http://localhost:8000/auth/github/callback`

Put the client ID and secret in `.env`, restart the API, and visit `/auth/github/login`.

## 7. Test `/users/me`

1. Complete OTP verification or an OAuth login and copy the `access_token` from the JSON response.
2. In `/docs`, open `GET /users/me`, click **Authorize**, and enter `Bearer YOUR_ACCESS_TOKEN` if prompted for the full header (or paste the token if the UI adds `Bearer` automatically).
3. Call the endpoint. It should return only the authenticated user's profile.

## Important security notes

- This is a learning starter, not production-ready authentication.
- Never commit `.env` or share provider secrets.
- Add rate limiting and abuse controls to OTP sending and verification before production.
- Use HTTPS in production and secure OAuth callbacks.
- Refresh tokens are currently stateless; implement token rotation, storage, and revocation for production.
- OAuth callbacks return token JSON directly for local testing. A real browser frontend should use a secure redirect/one-time-code flow rather than exposing tokens in a URL.
- Account linking is intentionally not done just because email addresses match.
- Use Alembic migrations for production schema management; `create_all` is used here only to make local learning easier.
- Add CSRF protections and carefully configure allowed frontend origins before deploying.
