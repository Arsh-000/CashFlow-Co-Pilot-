# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.database import supabase
from app.middleware.auth_middleware import get_current_user

router = APIRouter()


class BusinessSettings(BaseModel):
    starting_balance: float
    monthly_expenses: float


@router.get("/settings")
async def get_settings(current_user: dict = Depends(get_current_user)):
    business_id = current_user["business_id"]

    response = (
        supabase.table("businesses")
        .select("id, name, city, phone, starting_balance, monthly_expenses")
        .eq("id", business_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    return response.data[0]


@router.patch("/settings")
async def update_settings(
    body: BusinessSettings,
    current_user: dict = Depends(get_current_user),
):
    business_id = current_user["business_id"]

    response = (
        supabase.table("businesses")
        .upsert({
            "id": business_id,
            "starting_balance": body.starting_balance,
            "monthly_expenses": body.monthly_expenses,
        }, on_conflict="id")
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update settings")

    return {"status": "updated", "starting_balance": body.starting_balance, "monthly_expenses": body.monthly_expenses}