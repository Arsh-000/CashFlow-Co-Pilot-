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


def _fetch_invoices_and_risk(business_id: str) -> tuple[list[dict], dict[str, str]]:
    # Fetch invoices — no join needed, just what forecast_engine uses
    invoice_response = (
        supabase.table("invoices")
        .select("id, customer_id, due_date, amount, paid_amount, status")
        .eq("business_id", business_id)
        .execute()
    )
    invoices = invoice_response.data or []

    # Fetch customer risk levels separately — simple and reliable
    customer_response = (
        supabase.table("customers")
        .select("id, risk_level")
        .eq("business_id", business_id)
        .execute()
    )
    risk_levels = {
        row["id"]: (row.get("risk_level") or "amber").lower()
        for row in (customer_response.data or [])
    }

    return invoices, risk_levels


@router.post("/generate")
async def generate(
    body: ForecastRequest,
    current_user: dict = Depends(get_current_user),
):
    invoices, customer_risk_levels = _fetch_invoices_and_risk(current_user["business_id"])
    daily_expense = body.monthly_expenses / 30

    return compute_cash_forecast(
        invoices=invoices,
        customer_risk_levels=customer_risk_levels,
        starting_balance=body.starting_balance,
        forecast_days=body.forecast_days,
        daily_expense=daily_expense,
    )