import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

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