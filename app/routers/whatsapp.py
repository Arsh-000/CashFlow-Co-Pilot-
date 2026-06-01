# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.database import supabase
from app.middleware.auth_middleware import get_current_user
from app.services.forecast_engine import compute_cash_forecast
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


def _fetch_customer_risk_levels(business_id: str) -> dict[str, str]:
    response = (
        supabase.table("customers")
        .select("id, risk_level")
        .eq("business_id", business_id)
        .execute()
    )
    return {
        row["id"]: (row.get("risk_level") or "amber").lower()
        for row in (response.data or [])
    }


@router.post("/send-owner-summary")
async def send_owner_summary(current_user: dict = Depends(get_current_user)):
    business_id = current_user["business_id"]

    business_response = (
        supabase.table("businesses")
        .select("name, phone, starting_balance, monthly_expenses")
        .eq("id", business_id)
        .execute()
    )
    if not business_response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    business = business_response.data[0]
    if not business.get("phone"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Business phone not set")

    # Fetch invoices and metrics
    invoices = _fetch_invoices(business_id)
    metrics = compute_metrics(invoices)
    customer_summaries = compute_customer_summaries(invoices)
    top_risks = [
        c for c in customer_summaries if c.get("risk_level") in ("Red", "Amber")
    ][:3]

    # Fetch latest insight
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

    # Compute 30-day forecast
    starting_balance = float(business.get("starting_balance") or 0)
    monthly_expenses = float(business.get("monthly_expenses") or 0)
    customer_risk_levels = _fetch_customer_risk_levels(business_id)
    forecast = compute_cash_forecast(
        invoices=invoices,
        customer_risk_levels=customer_risk_levels,
        starting_balance=starting_balance,
        forecast_days=30,
        daily_expense=monthly_expenses / 30,
    )

    # Build message with forecast included
    message = build_owner_summary(
        business_name=business["name"],
        metrics=metrics,
        top_risks=top_risks,
        insight_summary=insight_summary,
        forecast=forecast,
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