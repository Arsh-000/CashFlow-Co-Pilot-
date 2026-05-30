from fastapi import APIRouter, Depends, HTTPException, status

from app.database import supabase
from app.middleware.auth_middleware import get_current_user
from app.services.ai_service import generate_insights, parse_insight_sections
from app.services.risk_engine import compute_customer_summaries, compute_metrics

router = APIRouter()


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
async def generate(current_user: dict = Depends(get_current_user)):
    business_id = current_user["business_id"]
    invoices = _fetch_invoices(business_id)

    metrics = compute_metrics(invoices)
    customer_summaries = compute_customer_summaries(invoices)

    raw_insights = generate_insights(invoices, metrics)
    parsed = parse_insight_sections(raw_insights)

    insight_record = {
        "business_id": business_id,
        "summary": parsed["summary"],
        "top_risks": parsed["top_risks"],
        "urgent_action": parsed["urgent_action"],
        "tamil_summary": parsed["tamil_summary"],
        "raw_content": raw_insights,
    }
    stored = supabase.table("insights").insert(insight_record).execute()

    return {
        "metrics": metrics,
        "customer_summaries": customer_summaries,
        "insights": parsed,
        "raw_insights": raw_insights,
        "insight_id": stored.data[0]["id"] if stored.data else None,
    }


@router.get("/latest")
async def latest(current_user: dict = Depends(get_current_user)):
    response = (
        supabase.table("insights")
        .select("*")
        .eq("business_id", current_user["business_id"])
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No insights found",
        )

    return response.data[0]
