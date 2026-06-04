# -*- coding: utf-8 -*-
import asyncio
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.middleware.auth_middleware import get_current_user

router = APIRouter()

REST_URL = f"{settings.SUPABASE_URL}/rest/v1"
AUTH_URL = f"{settings.SUPABASE_URL}/auth/v1"
SERVICE_KEY = settings.SUPABASE_SERVICE_KEY.strip()
ANON_KEY = settings.SUPABASE_ANON_KEY.strip()


def _headers():
    return {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }


def _auth_headers(token: str):
    return {
        "apikey": ANON_KEY,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# ─── Models ───────────────────────────────────────────────────────────────────

class BusinessSettings(BaseModel):
    starting_balance: float
    monthly_expenses: float


class BusinessProfile(BaseModel):
    name: str | None = None
    city: str | None = None
    phone: str | None = None
    language: str | None = None  # "en_ta" or "en"


class ChangePassword(BaseModel):
    new_password: str


# ─── Financial settings ───────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings(current_user: dict = Depends(get_current_user)):
    business_id = current_user["business_id"]

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{REST_URL}/businesses",
            headers=_headers(),
            params={
                "id": f"eq.{business_id}",
                "select": "id,name,city,phone,language,starting_balance,monthly_expenses",
            },
        )
        data = response.json()

    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    return data[0]


@router.patch("/settings")
async def update_settings(
    body: BusinessSettings,
    current_user: dict = Depends(get_current_user),
):
    business_id = current_user["business_id"]

    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{REST_URL}/businesses",
            headers={**_headers(), "Prefer": "return=representation"},
            params={"id": f"eq.{business_id}"},
            json={
                "starting_balance": body.starting_balance,
                "monthly_expenses": body.monthly_expenses,
            },
        )
        data = response.json()

    if response.status_code not in (200, 204):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(data))

    return {
        "status": "updated",
        "starting_balance": body.starting_balance,
        "monthly_expenses": body.monthly_expenses,
    }


# ─── Business profile ─────────────────────────────────────────────────────────

@router.patch("/profile")
async def update_profile(
    body: BusinessProfile,
    current_user: dict = Depends(get_current_user),
):
    """Update business name, city, phone, and language preference."""
    business_id = current_user["business_id"]

    # Only include fields that were actually provided
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update",
        )

    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{REST_URL}/businesses",
            headers={**_headers(), "Prefer": "return=representation"},
            params={"id": f"eq.{business_id}"},
            json=update_data,
        )
        data = response.json()

    if response.status_code not in (200, 204):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(data))

    return {"status": "updated", **update_data}


# ─── Account ──────────────────────────────────────────────────────────────────

@router.get("/account")
async def get_account(current_user: dict = Depends(get_current_user)):
    """Get current user account info — reads from auth middleware context."""
    user_id = current_user["user_id"]

    # Fetch email from Supabase auth.users via admin API
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{AUTH_URL}/admin/users/{user_id}",
            headers={
                "apikey": SERVICE_KEY,
                "Authorization": f"Bearer {SERVICE_KEY}",
            },
        )
        data = response.json()

    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not fetch account")

    return {
        "user_id": user_id,
        "email": data.get("email"),
        "created_at": data.get("created_at"),
    }


@router.patch("/account/password")
async def change_password(
    body: ChangePassword,
    current_user: dict = Depends(get_current_user),
):
    """Change password via Supabase Auth."""
    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{AUTH_URL}/user",
            headers=_auth_headers(current_user["token"]),
            json={"password": body.new_password},
        )
        data = response.json()

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=data.get("msg") or "Password change failed",
        )

    return {"status": "password updated"}


# ─── Data rights (DPDP Act compliance) ───────────────────────────────────────

@router.get("/export")
async def export_data(current_user: dict = Depends(get_current_user)):
    """Export all business data as JSON — required for DPDP Act compliance."""
    business_id = current_user["business_id"]

    async with httpx.AsyncClient() as client:
        # Fetch all tables in parallel
        businesses_r, customers_r, invoices_r, insights_r, events_r = await asyncio.gather(
            client.get(f"{REST_URL}/businesses", headers=_headers(), params={"id": f"eq.{business_id}"}),
            client.get(f"{REST_URL}/customers", headers=_headers(), params={"business_id": f"eq.{business_id}"}),
            client.get(f"{REST_URL}/invoices", headers=_headers(), params={"business_id": f"eq.{business_id}"}),
            client.get(f"{REST_URL}/insights", headers=_headers(), params={"business_id": f"eq.{business_id}"}),
            client.get(f"{REST_URL}/payment_events", headers=_headers(), params={"business_id": f"eq.{business_id}"}),
        )

    return {
        "export_version": "1.0",
        "business_id": business_id,
        "data": {
            "business": businesses_r.json(),
            "customers": customers_r.json(),
            "invoices": invoices_r.json(),
            "insights": insights_r.json(),
            "payment_events": events_r.json(),
        },
    }


@router.delete("/account")
async def delete_account(current_user: dict = Depends(get_current_user)):
    """
    Delete all business data and the auth account.
    DPDP Act compliance — right to erasure.
    WARNING: irreversible.
    """
    business_id = current_user["business_id"]
    user_id = current_user["user_id"]

    async with httpx.AsyncClient() as client:
        # Delete in correct order (child tables first)
        await client.delete(f"{REST_URL}/payment_events", headers=_headers(), params={"business_id": f"eq.{business_id}"})
        await client.delete(f"{REST_URL}/insights", headers=_headers(), params={"business_id": f"eq.{business_id}"})
        await client.delete(f"{REST_URL}/invoices", headers=_headers(), params={"business_id": f"eq.{business_id}"})
        await client.delete(f"{REST_URL}/customers", headers=_headers(), params={"business_id": f"eq.{business_id}"})
        await client.delete(f"{REST_URL}/businesses", headers=_headers(), params={"id": f"eq.{business_id}"})

        # Delete Supabase Auth user using admin key
        await client.delete(
            f"{AUTH_URL}/admin/users/{user_id}",
            headers={
                "apikey": SERVICE_KEY,
                "Authorization": f"Bearer {SERVICE_KEY}",
            },
        )

    return {"status": "account deleted"}