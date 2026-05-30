import httpx
from fastapi import HTTPException, Request, status

from app.config import settings
from app.database import http_client

AUTH_USER_URL = f"{settings.SUPABASE_URL}/auth/v1/user"
BUSINESSES_URL = f"{settings.SUPABASE_URL}/rest/v1/businesses"


async def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        print(f"[auth] Missing or invalid Authorization header: {auth_header!r}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    token = auth_header[7:].strip()
    print(f"[auth] Received token (first 50 chars): {token[:50]}")

    user_response = http_client.get(
        AUTH_USER_URL,
        headers={
            "apikey": settings.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {token}",
        },
    )
    print(f"[auth] GET /auth/v1/user -> {user_response.status_code}")
    print(f"[auth] GET /auth/v1/user body: {user_response.text}")

    if user_response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    user_id = user_response.json().get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    service_key = settings.SUPABASE_SERVICE_KEY.strip()
    business_response = http_client.get(
        BUSINESSES_URL,
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
        },
        params={
            "select": "id",
            "owner_id": f"eq.{user_id}",
        },
    )
    print(f"[auth] GET /rest/v1/businesses -> {business_response.status_code}")
    print(f"[auth] GET /rest/v1/businesses body: {business_response.text}")

    if business_response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    businesses = business_response.json()
    if not businesses:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    return {
        "user_id": user_id,
        "business_id": businesses[0]["id"],
    }
