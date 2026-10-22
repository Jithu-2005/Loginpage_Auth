
import asyncio
import httpx

from app.core.config import settings


BASE_URL = (
    "https://cpaas.messagecentral.com"
    "/auth/v1/authentication/token"
)


def redact_secrets(message: str) -> str:
    """Remove configured credentials from diagnostic output."""
    for secret in (
        settings.MESSAGE_CENTRAL_KEY,
        settings.MESSAGE_CENTRAL_CUSTOMER_ID,
        settings.MESSAGE_CENTRAL_EMAIL,
    ):
        if secret:
            message = message.replace(secret, "[REDACTED]")

    return message[:500]


async def main() -> None:
    if not all(
        [
            settings.MESSAGE_CENTRAL_CUSTOMER_ID,
            settings.MESSAGE_CENTRAL_EMAIL,
            settings.MESSAGE_CENTRAL_KEY,
            settings.MESSAGE_CENTRAL_COUNTRY_CODE,
        ]
    ):
        print("ERROR: Message Central configuration is incomplete.")
        print("Check your local .env file.")
        return

    params = {
        "customerId": settings.MESSAGE_CENTRAL_CUSTOMER_ID,
        "key": settings.MESSAGE_CENTRAL_KEY,
        "scope": "NEW",
        "country": settings.MESSAGE_CENTRAL_COUNTRY_CODE,
        "email": settings.MESSAGE_CENTRAL_EMAIL,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                BASE_URL,
                params=params,
                headers={"accept": "*/*"},
            )

        print("HTTP status:", response.status_code)

        try:
            data = response.json()
        except ValueError:
            print("Provider returned a non-JSON response.")
            print("Response preview:", redact_secrets(response.text))
            return

        print("Response fields:", list(data.keys()))

        if response.is_error:
            print("Provider HTTP error:", response.status_code)

        error = data.get("error")
        if error:
            if isinstance(error, (dict, list)):
                import json
                error = json.dumps(error)
            print("Provider error:", redact_secrets(str(error)))

        token = data.get("token")
        if token:
            print("Authentication token received: Yes")
            print("Token value: [HIDDEN]")
        else:
            print("Authentication token received: No")

        if not error and not token:
            print("No token or explicit error was returned.")
            print("Check the provider's authentication documentation.")

    except httpx.TimeoutException:
        print("ERROR: Request timed out while contacting Message Central.")
    except httpx.HTTPError as exc:
        print("ERROR: HTTP request failed:", type(exc).__name__)
    except Exception as exc:
        print("ERROR:", type(exc).__name__)


if __name__ == "__main__":
    asyncio.run(main())
