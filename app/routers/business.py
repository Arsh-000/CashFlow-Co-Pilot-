# -*- coding: utf-8 -*-
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.middleware.auth_middleware import get_current_user

router = APIRouter()

REST_URL = f"{settings.SUPABASE_URL}/rest/v1"
SERVICE_KEY = settings.SUPABASE_SERVICE_KEY.strip()


def _headers():
    return {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }


class BusinessSettings(BaseModel):
    starting_balance: float
    monthly_expenses: float


@router.get("/settings")
async def get_settings(current_user: dict = Depends(get_current_user)):
    business_id = current_user["business_id"]

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{REST_URL}/businesses",
            headers=_headers(),
            params={"id": f"eq.{business_id}", "select": "id,name,city,phone,starting_balance,monthly_expenses"},
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