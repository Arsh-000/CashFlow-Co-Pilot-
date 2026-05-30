from collections import defaultdict
from datetime import date, datetime


def get_days_overdue(due_date: str) -> int:
    parsed = datetime.strptime(due_date[:10], "%Y-%m-%d").date()
    return max(0, (date.today() - parsed).days)


def score_risk_level(days_overdue: int) -> str:
    if days_overdue >= 31:
        return "Red"
    if days_overdue >= 1:
        return "Amber"
    return "Green"


def compute_customer_summaries(invoices: list[dict]) -> list[dict]:
    customers: dict[str, dict] = defaultdict(
        lambda: {"total_outstanding": 0.0, "max_days_overdue": 0}
    )

    for invoice in invoices:
        if invoice.get("status") == "paid":
            continue

        name = invoice.get("customer_name") or invoice.get("customers", {}).get("name", "Unknown")
        amount = float(invoice.get("amount", 0))
        due_date = invoice.get("due_date", "")
        days_overdue = get_days_overdue(due_date) if due_date else 0

        customers[name]["total_outstanding"] += amount
        customers[name]["max_days_overdue"] = max(
            customers[name]["max_days_overdue"], days_overdue
        )

    summaries = []
    for name, data in customers.items():
        risk_level = score_risk_level(data["max_days_overdue"])
        summaries.append(
            {
                "customer_name": name,
                "total_outstanding": round(data["total_outstanding"], 2),
                "max_days_overdue": data["max_days_overdue"],
                "risk_level": risk_level,
            }
        )

    summaries.sort(key=lambda x: x["total_outstanding"], reverse=True)
    return summaries


def compute_metrics(invoices: list[dict]) -> dict:
    total_receivables = 0.0
    amount_collected = 0.0
    overdue_amount = 0.0
    at_risk_amount = 0.0

    for invoice in invoices:
        amount = float(invoice.get("amount", 0))
        status = invoice.get("status", "unpaid")
        due_date = invoice.get("due_date", "")

        if status == "paid":
            amount_collected += amount
        else:
            total_receivables += amount
            days_overdue = get_days_overdue(due_date) if due_date else 0
            if days_overdue > 0:
                overdue_amount += amount
            risk = score_risk_level(days_overdue)
            if risk in ("Red", "Amber"):
                at_risk_amount += amount

    return {
        "total_receivables": round(total_receivables, 2),
        "amount_collected": round(amount_collected, 2),
        "overdue_amount": round(overdue_amount, 2),
        "at_risk_amount": round(at_risk_amount, 2),
    }
