from fastapi import APIRouter, Depends

from app.database import supabase
from app.middleware.auth_middleware import get_current_user
from app.services.risk_engine import compute_customer_summaries, compute_metrics

router = APIRouter()


@router.get("/summary")
async def summary(current_user: dict = Depends(get_current_user)):
    business_id = current_user["business_id"]

    invoice_response = (
        supabase.table("invoices")
        .select("*, customers(name)")
        .eq("business_id", business_id)
        .order("due_date")
        .execute()
    )

    invoices = []
    for row in invoice_response.data or []:
        customer_name = row.get("customers", {}).get("name") if row.get("customers") else None
        invoices.append({**row, "customer_name": customer_name})

    metrics = compute_metrics(invoices)
    customer_summaries = compute_customer_summaries(invoices)

    insight_response = (
        supabase.table("insights")
        .select("*")
        .eq("business_id", business_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    latest_insight = insight_response.data[0] if insight_response.data else None

    return {
        "metrics": metrics,
        "customers": customer_summaries,
        "invoices": invoices,
        "latest_insight": latest_insight,
    }
    