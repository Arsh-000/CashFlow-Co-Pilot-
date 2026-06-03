import csv
import io
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.database import supabase
from app.middleware.auth_middleware import get_current_user

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

    # Fetch the invoice — verify it belongs to this business
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

    # Determine payment date
    if body.payment_date:
        payment_date = datetime.strptime(body.payment_date[:10], "%Y-%m-%d").date()
    else:
        payment_date = date.today()

    # Compute new paid_amount and status
    new_paid_amount = float(invoice["paid_amount"] or 0) + body.amount_paid
    total_amount = float(invoice["amount"] or 0)

    if new_paid_amount >= total_amount:
        new_status = "paid"
        new_paid_amount = total_amount  # cap at invoice amount
    else:
        new_status = "partial"

    # Update invoice
    supabase.table("invoices").update({
        "paid_amount": new_paid_amount,
        "status": new_status,
        "payment_date": payment_date.isoformat(),
    }).eq("id", invoice_id).execute()

    # Record payment event
    days_from_due = _compute_days_from_due(invoice.get("due_date"), payment_date)

    supabase.table("payment_events").insert({
        "invoice_id": invoice_id,
        "business_id": business_id,
        "customer_id": invoice["customer_id"],
        "payment_date": payment_date.isoformat(),
        "amount_paid": body.amount_paid,
        "days_from_due_date": days_from_due,
    }).execute()

    return {
        "status": "updated",
        "invoice_id": invoice_id,
        "new_status": new_status,
        "paid_amount": new_paid_amount,
        "payment_date": payment_date.isoformat(),
        "days_from_due_date": days_from_due,
    }


@router.get("/list")
async def list_invoices(current_user: dict = Depends(get_current_user)):
    response = (
        supabase.table("invoices")
        .select("*, customers(name)")
        .eq("business_id", current_user["business_id"])
        .order("due_date")
        .execute()
    )

    invoices = []
    for row in response.data or []:
        customer_name = row.get("customers", {}).get("name") if row.get("customers") else None
        invoices.append({**row, "customer_name": customer_name})

    return invoices