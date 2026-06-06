import csv
import io
from datetime import date, datetime

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.config import settings
from app.database import supabase
from app.middleware.auth_middleware import get_current_user

_REST_URL = f"{settings.SUPABASE_URL}/rest/v1"
_SERVICE_KEY = settings.SUPABASE_SERVICE_KEY.strip()

def _db_headers():
    return {
        "apikey": _SERVICE_KEY,
        "Authorization": f"Bearer {_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

router = APIRouter()


def _find_or_create_customer(business_id: str, customer_name: str, phone: str | None = None) -> str:
    existing = (
        supabase.table("customers")
        .select("id")
        .eq("business_id", business_id)
        .eq("name", customer_name)
        .execute()
    )
    if existing.data:
        return existing.data[0]["id"]

    customer_data: dict = {"business_id": business_id, "name": customer_name}
    if phone:
        customer_data["phone"] = phone

    created = (
        supabase.table("customers")
        .insert(customer_data)
        .execute()
    )
    return created.data[0]["id"]


def _invoice_exists(business_id: str, invoice_number: str) -> bool:
    result = (
        supabase.table("invoices")
        .select("id")
        .eq("business_id", business_id)
        .eq("invoice_number", invoice_number)
        .execute()
    )
    return bool(result.data)


def _parse_date(value: str) -> str | None:
    if not value or not value.strip():
        return None
    return value.strip()


def _parse_float(value: str) -> float:
    try:
        return float(value or 0)
    except (ValueError, TypeError):
        return 0.0


def _compute_days_from_due(due_date_str: str, payment_date: date) -> int | None:
    if not due_date_str:
        return None
    try:
        due = datetime.strptime(due_date_str[:10], "%Y-%m-%d").date()
        return (payment_date - due).days
    except ValueError:
        return None


class MarkPaidRequest(BaseModel):
    amount_paid: float
    payment_date: str | None = None  # YYYY-MM-DD, defaults to today


@router.post("/upload/csv")
async def upload_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV",
        )

    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    business_id = current_user["business_id"]
    inserted = 0
    skipped = 0

    for row in reader:
        customer_name = row.get("customer_name") or row.get("customer") or row.get("name")
        if not customer_name:
            continue

        invoice_number = row.get("invoice_number", "").strip()

        if invoice_number and _invoice_exists(business_id, invoice_number):
            skipped += 1
            continue

        phone = row.get("phone", "").strip() or None
        customer_id = _find_or_create_customer(business_id, customer_name.strip(), phone)

        invoice_data = {
            "business_id": business_id,
            "customer_id": customer_id,
            "amount": _parse_float(row.get("amount")),
            "paid_amount": _parse_float(row.get("paid_amount")),
            "due_date": _parse_date(row.get("due_date")),
            "invoice_date": _parse_date(row.get("invoice_date")),
            "status": row.get("status", "unpaid").strip() or "unpaid",
        }

        if invoice_number:
            invoice_data["invoice_number"] = invoice_number

        supabase.table("invoices").insert(invoice_data).execute()
        inserted += 1

    return {
        "message": f"Successfully imported {inserted} invoices",
        "inserted": inserted,
        "skipped": skipped,
    }


@router.post("/{invoice_id}/mark-paid")
async def mark_paid(
    invoice_id: str,
    body: MarkPaidRequest,
    current_user: dict = Depends(get_current_user),
):
    business_id = current_user["business_id"]

    invoice_response = (
        supabase.table("invoices")
        .select("id, business_id, customer_id, amount, paid_amount, due_date, status")
        .eq("id", invoice_id)
        .eq("business_id", business_id)
        .execute()
    )

    if not invoice_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    invoice = invoice_response.data[0]

    if body.payment_date:
        payment_date = datetime.strptime(body.payment_date[:10], "%Y-%m-%d").date()
    else:
        payment_date = date.today()

    new_paid_amount = float(invoice["paid_amount"] or 0) + body.amount_paid
    total_amount = float(invoice["amount"] or 0)

    if new_paid_amount >= total_amount:
        new_status = "paid"
        new_paid_amount = total_amount
    else:
        new_status = "partial"

    days_from_due = _compute_days_from_due(invoice.get("due_date"), payment_date)

    async with httpx.AsyncClient() as client:
        await client.patch(
            f"{_REST_URL}/invoices",
            headers=_db_headers(),
            params={"id": f"eq.{invoice_id}"},
            json={
                "paid_amount": new_paid_amount,
                "status": new_status,
                "payment_date": payment_date.isoformat(),
            },
        )
        await client.post(
            f"{_REST_URL}/payment_events",
            headers=_db_headers(),
            json={
                "invoice_id": invoice_id,
                "business_id": business_id,
                "customer_id": invoice["customer_id"],
                "payment_date": payment_date.isoformat(),
                "amount_paid": body.amount_paid,
                "days_from_due_date": days_from_due,
            },
        )

    return {
        "status": "updated",
        "invoice_id": invoice_id,
        "new_status": new_status,
        "paid_amount": new_paid_amount,
        "payment_date": payment_date.isoformat(),
        "days_from_due_date": days_from_due,
    }


@router.get("/list")
async def list_invoices(
    current_user: dict = Depends(get_current_user),
    search: str | None = None,
    status: str | None = None,
    customer_id: str | None = None,
):
    query = (
        supabase.table("invoices")
        .select("*, customers(name, risk_level)")
        .eq("business_id", current_user["business_id"])
        .order("due_date")
    )

    if status:
        query = query.eq("status", status.lower())

    if customer_id:
        query = query.eq("customer_id", customer_id)

    response = query.execute()

    invoices = []
    for row in response.data or []:
        customer = row.get("customers") or {}
        customer_name = customer.get("name") if customer else None
        customer_risk = customer.get("risk_level") if customer else None
        row_with_name = {
            **row,
            "customer_name": customer_name,
            "risk_level": customer_risk,  # ← expose customer risk on invoice
        }

        if search:
            search_lower = search.lower()
            name_match = customer_name and search_lower in customer_name.lower()
            number_match = search_lower in (row.get("invoice_number") or "").lower()
            if not name_match and not number_match:
                continue

        invoices.append(row_with_name)

    return invoices


# ── Payment history for a customer ────────────────────────────────────────────

@router.get("/customers/{customer_id}/payment-history")
async def get_payment_history(
    customer_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Return payment_events for a specific customer.
    Used by the frontend to show real avg_delay and payment history.
    """
    business_id = current_user["business_id"]

    # Verify customer belongs to this business
    customer_check = (
        supabase.table("customers")
        .select("id, name")
        .eq("id", customer_id)
        .eq("business_id", business_id)
        .execute()
    )

    if not customer_check.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    # Fetch payment events for this customer
    events_response = (
        supabase.table("payment_events")
        .select("id, invoice_id, payment_date, amount_paid, days_from_due_date, created_at")
        .eq("customer_id", customer_id)
        .eq("business_id", business_id)
        .order("payment_date", desc=True)
        .execute()
    )

    events = events_response.data or []

    # Compute avg_days_from_due from real data
    days_values = [
        e["days_from_due_date"]
        for e in events
        if e.get("days_from_due_date") is not None
    ]

    avg_days_from_due = round(sum(days_values) / len(days_values)) if days_values else None
    total_payments = len(events)
    late_payments = sum(1 for d in days_values if d > 0)
    on_time_payments = total_payments - late_payments

    return {
        "customer_id": customer_id,
        "customer_name": customer_check.data[0]["name"],
        "avg_days_from_due": avg_days_from_due,
        "total_payments": total_payments,
        "late_payments": late_payments,
        "on_time_payments": on_time_payments,
        "payment_events": events,
    }


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
    "image/gif": "image/gif",
}


@router.post("/upload/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    from app.services.ocr_service import extract_invoices_from_image

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {content_type}. Supported: JPEG, PNG, WEBP, GIF",
        )

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 10MB",
        )

    try:
        extracted_rows = await extract_invoices_from_image(
            image_bytes=image_bytes,
            media_type=ALLOWED_IMAGE_TYPES[content_type],
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    if not extracted_rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No invoice data found in image",
        )

    business_id = current_user["business_id"]
    inserted = 0
    skipped = 0

    for row in extracted_rows:
        customer_name = row.get("customer_name", "").strip()
        if not customer_name:
            continue

        invoice_number = str(row.get("invoice_number", "")).strip()

        if invoice_number and _invoice_exists(business_id, invoice_number):
            skipped += 1
            continue

        phone = str(row.get("phone", "")).strip() or None
        customer_id = _find_or_create_customer(business_id, customer_name, phone)

        invoice_data = {
            "business_id": business_id,
            "customer_id": customer_id,
            "amount": float(row.get("amount") or 0),
            "paid_amount": float(row.get("paid_amount") or 0),
            "due_date": row.get("due_date") or None,
            "invoice_date": row.get("invoice_date") or None,
            "status": row.get("status", "unpaid") or "unpaid",
        }

        if invoice_number:
            invoice_data["invoice_number"] = invoice_number

        supabase.table("invoices").insert(invoice_data).execute()
        inserted += 1

    return {
        "message": f"Successfully extracted and imported {inserted} invoices from image",
        "inserted": inserted,
        "skipped": skipped,
        "extracted_data": extracted_rows,
    }