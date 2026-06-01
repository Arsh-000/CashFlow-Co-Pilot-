# -*- coding: utf-8 -*-
import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

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


def _build_business_context(invoices: list[dict], metrics: dict, customer_summaries: list[dict]) -> str:
    """Build a concise business context string to pass to the AI."""
    lines = [
        "=== BUSINESS DATA ===",
        f"Total Receivables: Rs {metrics.get('total_receivables', 0):,.0f}",
        f"Amount Collected: Rs {metrics.get('amount_collected', 0):,.0f}",
        f"Overdue Amount: Rs {metrics.get('overdue_amount', 0):,.0f}",
        f"At Risk Amount: Rs {metrics.get('at_risk_amount', 0):,.0f}",
        "",
        "=== CUSTOMERS ===",
    ]

    for c in customer_summaries:
        name = c.get("name", "Unknown")
        outstanding = c.get("total_outstanding", 0)
        days = c.get("max_overdue_days", 0)
        risk = c.get("risk_level", "Unknown")
        lines.append(f"- {name}: Rs {outstanding:,.0f} outstanding, {days} days overdue, {risk} risk")

    lines.append("")
    lines.append("=== INVOICES ===")
    for inv in invoices[:20]:  # limit to 20 to stay within token limits
        lines.append(
            f"- Invoice {inv.get('invoice_number', 'N/A')}: "
            f"Customer={inv.get('customer_name', 'Unknown')}, "
            f"Amount=Rs {float(inv.get('amount', 0)):,.0f}, "
            f"Paid=Rs {float(inv.get('paid_amount', 0)):,.0f}, "
            f"Status={inv.get('status', 'unknown')}, "
            f"Due={inv.get('due_date', 'N/A')}"
        )

    return "\n".join(lines)


async def _ask_groq(question: str, context: str) -> str:
    """Send question + business context to Groq and get an answer."""
    import httpx
    from app.config import settings

    system_prompt = (
        "You are Crest, an AI financial assistant for a Tamil Nadu SMB owner. "
        "You have access to their business invoice and customer data. "
        "Answer questions about their finances clearly and concisely. "
        "Use Rs format for amounts. Be direct and actionable. "
        "Reply in English only. No markdown, no bullet symbols, plain text only."
    )

    user_message = f"{context}\n\n=== QUESTION ===\n{question}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "max_tokens": 500,
                "temperature": 0.3,
            },
        )
        data = response.json()

    if "choices" not in data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Groq API error: {data.get('error', {}).get('message', 'Unknown error')}",
        )

    return data["choices"][0]["message"]["content"].strip()


class ChatRequest(BaseModel):
    question: str


@router.post("/chat")
async def chat(
    body: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    if not body.question or not body.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty",
        )

    business_id = current_user["business_id"]
    invoices = _fetch_invoices(business_id)

    if not invoices:
        return {"answer": "No invoice data found. Please upload your invoices first to get financial insights."}

    metrics = compute_metrics(invoices)
    customer_summaries = compute_customer_summaries(invoices)
    context = _build_business_context(invoices, metrics, customer_summaries)
    answer = await _ask_groq(body.question.strip(), context)

    return {"answer": answer}


@router.post("/generate")
async def generate(current_user: dict = Depends(get_current_user)):
    business_id = current_user["business_id"]
    invoices = _fetch_invoices(business_id)

    if not invoices:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No invoices found. Upload invoices first.",
        )

    metrics = compute_metrics(invoices)
    customer_summaries = compute_customer_summaries(invoices)

    raw_insights = generate_insights(invoices, metrics)
    parsed = parse_insight_sections(raw_insights)

    top_risks = parsed["top_risks"]
    if isinstance(top_risks, list):
        top_risks_json = top_risks
    else:
        top_risks_json = [top_risks] if top_risks else []

    insight_record = {
        "business_id": business_id,
        "summary": parsed["summary"],
        "top_risks": top_risks_json,
        "urgent_action": parsed["urgent_action"],
        "tamil_summary": parsed["tamil_summary"],
        "raw_response": raw_insights,
    }
    stored = supabase.table("insights").insert(insight_record).execute()

    return {
        "metrics": metrics,
        "customers": customer_summaries,
        "summary": parsed["summary"],
        "top_risks": top_risks_json,
        "urgent_action": parsed["urgent_action"],
        "tamil_summary": parsed["tamil_summary"],
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