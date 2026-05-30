import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.config import settings
from app.database import AUTH_URL, http_client, supabase

router = APIRouter()


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    business_name: str
    city: str
    phone: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _auth_request_headers() -> dict[str, str]:
    return {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }


@router.post("/signup")
async def signup(body: SignupRequest):
    try:
        response = http_client.post(
            f"{AUTH_URL}/signup",
            headers=_auth_request_headers(),
            json={"email": body.email, "password": body.password},
        )
        if response.status_code >= 400:
            detail = response.json().get("msg") or response.json().get("message") or response.text
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

        payload = response.json()
        user = payload.get("user") or payload
        user_id = user.get("id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user",
            )

        supabase.table("businesses").insert(
            {
                "owner_id": user_id,
                "name": body.business_name,
                "city": body.city,
                "phone": body.phone,
            }
        ).execute()

        return {"message": "Signup successful"}
    except HTTPException:
        raise
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/login")
async def login(body: LoginRequest):
    try:
        response = http_client.post(
            f"{AUTH_URL}/token",
            headers=_auth_request_headers(),
            params={"grant_type": "password"},
            json={"email": body.email, "password": body.password},
        )
        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        access_token = response.json().get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        return {"access_token": access_token}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
