import hashlib
import logging
import time

import httpx
from fastapi import HTTPException, Request, status

from app.config import settings
from app.database import http_client

logger = logging.getLogger(__name__)

AUTH_USER_URL = f"{settings.SUPABASE_URL}/auth/v1/user"
BUSINESSES_URL = f"{settings.SUPABASE_URL}/rest/v1/businesses"

# Cache structure: token_hash → {user_id, business_id, expires_at}
# Token verified once, cached for 10 minutes
# Clears on Railway redeploy (acceptable)
_auth_cache: dict[str, dict] = {}
CACHE_TTL_SECONDS = 600  # 10 minutes


def _get_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _get_cached_user(token_hash: str) -> dict | None:
    entry = _auth_cache.get(token_hash)
    if not entry:
        return None
    if time.time() > entry["expires_at"]:
        del _auth_cache[token_hash]
        return None
    return entry


async def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    token = auth_header[7:].strip()
    token_hash = _get_token_hash(token)

    # Return from cache if valid — skips both Supabase calls (~1 second saved)
    cached = _get_cached_user(token_hash)
    if cached:
        return {
            "user_id": cached["user_id"],
            "business_id": cached["business_id"],
            "token": token,
        }

    # Cache miss — verify token with Supabase Auth
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

    # Look up business_id
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

    # Cache both user_id and business_id for 10 minutes
    _auth_cache[token_hash] = {
        "user_id": user_id,
        "business_id": business_id,
        "expires_at": time.time() + CACHE_TTL_SECONDS,
    }

    return {
        "user_id": user_id,
        "business_id": business_id,
        "token": token,
    }