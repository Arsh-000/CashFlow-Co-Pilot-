from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.database import supabase
from app.middleware.auth_middleware import get_current_user
from app.services.forecast_engine import compute_cash_forecast

router = APIRouter()


class ForecastRequest(BaseModel):
    starting_balance: float
    monthly_expenses: float = 0.0
    forecast_days: int = Field(default=30, ge=1, le=365)


def _fetch_invoices(business_id: str) -> list[dict]:
    response = (
        supabase.table("invoices")
        .select("*, customers(name)")
        .eq("business_id", business_id)
        .execute()
    )

    invoices = []
    for row in response.data or []:
        customer_name = row.get("customers", {}).get("name") if row.get("customers") else None
        invoices.append({**row, "customer_name": customer_name})
    return invoices


@router.post("/generate")
async def generate(
    body: ForecastRequest,
    current_user: dict = Depends(get_current_user),
):
    invoices = _fetch_invoices(current_user["business_id"])
    daily_expense = body.monthly_expenses / 30

    return compute_cash_forecast(
        invoices=invoices,
        starting_balance=body.starting_balance,
        forecast_days=body.forecast_days,
        daily_expense=daily_expense,
    )
