import hashlib
import logging

import httpx
from fastapi import HTTPException, Request, status

from app.config import settings
from app.database import http_client

logger = logging.getLogger(__name__)

AUTH_USER_URL = f"{settings.SUPABASE_URL}/auth/v1/user"
BUSINESSES_URL = f"{settings.SUPABASE_URL}/rest/v1/businesses"

# In-memory cache: token_hash → business_id
# Cuts auth overhead from ~400ms to ~200ms per request
# Cache is per-process — clears on Railway redeploy (acceptable)
_business_id_cache: dict[str, str] = {}


async def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    token = auth_header[7:].strip()

    # Step 1 — verify token with Supabase Auth (always required, ~150-200ms)
    user_response = http_client.get(
        AUTH_USER_URL,
        headers={
            "apikey": settings.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {token}",
        },
    )

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

    # Step 2 — look up business_id (cached after first call)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    if token_hash in _business_id_cache:
        business_id = _business_id_cache[token_hash]
        logger.debug(f"[auth] business_id from cache for user {user_id}")
    else:
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

        business_id = businesses[0]["id"]
        _business_id_cache[token_hash] = business_id
        logger.debug(f"[auth] business_id cached for user {user_id}")

    return {
        "user_id": user_id,
        "business_id": business_id,
        "token": token,
    }