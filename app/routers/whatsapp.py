from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.database import supabase
from app.middleware.auth_middleware import get_current_user
from app.services.risk_engine import compute_customer_summaries, compute_metrics
from app.services.whatsapp_service import (
    build_customer_reminder,
    build_owner_summary,
    send_whatsapp,
)

router = APIRouter()


class WhatsAppTestRequest(BaseModel):
    to: str
    message: str = "test"


def _fetch_invoices(business_id: str) -> list[dict]:
    response = (
        supabase.table("invoices")
        .select("*, customers(name, phone, risk_level)")
        .eq("business_id", business_id)
        .execute()
    )

    invoices = []
    for row in response.data or []:
        customer = row.get("customers") or {}
        invoices.append(
            {
                **row,
                "customer_name": customer.get("name"),
                "customer_phone": customer.get("phone"),
                "customer_risk_level": customer.get("risk_level"),
            }
        )
    return invoices


@router.post("/send-owner-summary")
async def send_owner_summary(current_user: dict = Depends(get_current_user)):
    business_id = current_user["business_id"]

    business_response = (
        supabase.table("businesses")
        .select("name, phone")
        .eq("id", business_id)
        .execute()
    )
    if not business_response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    business = business_response.data[0]
    if not business.get("phone"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Business phone not set")

    invoices = _fetch_invoices(business_id)
    metrics = compute_metrics(invoices)
    customer_summaries = compute_customer_summaries(invoices)
    top_risks = [
        c for c in customer_summaries if c.get("risk_level") in ("Red", "Amber")
    ][:3]

    insight_response = (
        supabase.table("insights")
        .select("summary")
        .eq("business_id", business_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    insight_summary = ""
    if insight_response.data:
        insight_summary = insight_response.data[0].get("summary") or ""

    message = build_owner_summary(
        business_name=business["name"],
        metrics=metrics,
        top_risks=top_risks,
        insight_summary=insight_summary,
    )

    result = await send_whatsapp(business["phone"], message)
    return {"status": "sent", "to": business["phone"], "twilio": result}


@router.post("/send-reminders")
async def send_reminders(current_user: dict = Depends(get_current_user)):
    business_id = current_user["business_id"]

    business_response = (
        supabase.table("businesses")
        .select("name")
        .eq("id", business_id)
        .execute()
    )
    if not business_response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    business_name = business_response.data[0]["name"]

    # Send to ALL customers with a phone number — not just Red/Amber
    customers_response = (
        supabase.table("customers")
        .select("id, name, phone, risk_level")
        .eq("business_id", business_id)
        .execute()
    )
    customers_with_phone = [
        c for c in (customers_response.data or [])
        if c.get("phone")
    ]

    if not customers_with_phone:
        return {"status": "no_customers", "sent": 0, "results": []}

    invoices = _fetch_invoices(business_id)
    results = []

    for customer in customers_with_phone:
        customer_invoices = [
            inv for inv in invoices if inv.get("customer_id") == customer["id"]
        ]
        # Only send if customer has unpaid invoices
        if not any(inv.get("status") != "paid" for inv in customer_invoices):
            continue

        message = build_customer_reminder(
            customer_name=customer["name"],
            business_name=business_name,
            invoices=customer_invoices,
        )
        twilio_result = await send_whatsapp(customer["phone"], message)
        results.append(
            {
                "customer_id": customer["id"],
                "customer_name": customer["name"],
                "to": customer["phone"],
                "twilio_sid": twilio_result.get("sid"),
            }
        )

    return {"status": "sent", "sent": len(results), "results": results}


@router.post("/test")
async def test_whatsapp(
    body: WhatsAppTestRequest,
    current_user: dict = Depends(get_current_user),
):
    result = await send_whatsapp(body.to, body.message)
    return {"status": "sent", "to": body.to, "twilio": result}