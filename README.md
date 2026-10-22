# Auth API (FastAPI + Swagger + Mobile OTP + Google + GitHub)

## Run (VS Code terminal)
```bash
python -m venv venv
venv\Scripts\activate            # Windows      (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # Windows      (Mac/Linux: cp .env.example .env)
python run.py
```
Open **http://localhost:3000/docs** (Swagger UI).
(Alternative: `uvicorn app.main:app --reload --port 3000`)

In VS Code press `Ctrl+Shift+P` -> **Python: Select Interpreter** -> choose the `venv` one.

## Project structure
```
app/
  main.py            FastAPI app, Swagger config, error handlers
  config.py          reads .env
  schemas.py         request / response models (these generate the Swagger docs)
  dependencies.py    Bearer auth ("Authorize" button) + rate limiter
  errors.py          AppError
  routes/auth.py     all endpoints
  services/
    otp.py           Message Central OTP + console OTP
    oauth.py         Google + GitHub
    tokens.py        JWT
    users.py         in-memory users
run.py               starts the server
```

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | /api/auth/otp/send | send OTP to a phone number |
| POST | /api/auth/login | login: `mobile_otp` / `google` / `github` |
| GET | /api/auth/google, /google/callback | browser Google login |
| GET | /api/auth/github, /github/callback | browser GitHub login |
| GET | /api/auth/me | protected route (Bearer token) |

## Test 1 - Mobile OTP (works with zero setup)
1. `POST /api/auth/otp/send` with `{ "phone": "+919876543210" }`
2. The OTP appears in the VS Code terminal and in the response (`devOtp`).
3. `POST /api/auth/login` with `{ "provider": "mobile_otp", "phone": "+919876543210", "otp": "<otp>" }`
4. Copy `accessToken` -> click **Authorize** in Swagger -> call `GET /api/auth/me`.

## Test 2 - Google
1. Create an OAuth client (Web) at https://console.cloud.google.com/apis/credentials
   Redirect URI: `http://localhost:3000/api/auth/google/callback`
2. Put `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` in `.env`, restart.
3. Open `http://localhost:3000/api/auth/google` in a browser -> the JSON response contains your JWT.
   (Mobile/SPA: send the Google `idToken` to `POST /api/auth/login` with `provider: "google"`.)

## Test 3 - GitHub
1. Create an OAuth App at https://github.com/settings/developers
   Callback URL: `http://localhost:3000/api/auth/github/callback`
2. Put `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` in `.env`, restart.
3. Open `http://localhost:3000/api/auth/github` in a browser -> JSON with your JWT.

## Real SMS with Message Central (optional)
1. Sign up at https://console.messagecentral.com (free test credits are given).
2. Note your **Customer ID** and account **password**.
3. In `.env`:
```
SMS_PROVIDER=messagecentral
MESSAGECENTRAL_CUSTOMER_ID=C-XXXXXXXXXXXX
MESSAGECENTRAL_PASSWORD=your-account-password
```
4. Restart. Send phone numbers in E.164 format (e.g. `+919876543210`).

How it works: the server gets an auth token from Message Central (cached automatically),
calls `/verification/v3/send`, keeps the returned `verificationId` for that phone, and on login calls
`/verification/v3/validateOtp`. Message Central generates, sends, expires and checks the OTP.

## Notes
- Users are stored in memory (lost on restart) - swap `app/services/users.py` for a DB.
- Console mode: OTPs are HMAC-hashed, expire in 5 min, allow 5 attempts, 30s resend cooldown.
- Message Central mode: Message Central handles generation, expiry and attempt limits.
- Login endpoints are rate limited (20 requests/min per IP).
