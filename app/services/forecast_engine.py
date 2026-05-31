from collections import defaultdict
from datetime import date, datetime, timedelta


def _parse_date(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def _get_days_overdue(due_date: str) -> int:
    return max(0, (date.today() - _parse_date(due_date)).days)


def _customer_delay_days(invoices: list[dict], customer_name: str) -> int:
    customer_invoices = [
        inv
        for inv in invoices
        if (inv.get("customer_name") or "Unknown") == customer_name
    ]
    if len(customer_invoices) <= 1:
        return 15

    overdue_days = [
        _get_days_overdue(inv["due_date"])
        for inv in customer_invoices
        if inv.get("due_date")
    ]
    if not overdue_days:
        return 15
    return round(sum(overdue_days) / len(overdue_days))


def compute_cash_forecast(
    invoices: list[dict],
    starting_balance: float,
    forecast_days: int = 30,
    daily_expense: float = 0.0,
) -> dict:
    today = date.today()
    inflows_by_date: dict[date, float] = defaultdict(float)

    for invoice in invoices:
        status = invoice.get("status", "unpaid")
        if status == "paid":
            continue

        amount = float(invoice.get("amount", 0))
        paid_amount = float(invoice.get("paid_amount", 0))
        outstanding = amount - paid_amount
        if outstanding <= 0:
            continue

        due_date = invoice.get("due_date")
        if not due_date:
            continue

        customer_name = invoice.get("customer_name") or "Unknown"
        delay_days = _customer_delay_days(invoices, customer_name)
        expected_payment_date = _parse_date(due_date) + timedelta(days=delay_days)
        if expected_payment_date < today:
            expected_payment_date = today

        inflows_by_date[expected_payment_date] += outstanding

    daily_forecast = []
    running_balance = starting_balance
    lowest_balance = starting_balance
    shortage_date = None
    days_until_shortage = None

    for offset in range(forecast_days + 1):
        forecast_date = today + timedelta(days=offset)
        expected_inflow = round(inflows_by_date.get(forecast_date, 0.0), 2)
        running_balance = running_balance + expected_inflow - daily_expense
        running_balance = round(running_balance, 2)

        if running_balance < lowest_balance:
            lowest_balance = running_balance

        if shortage_date is None and running_balance < 0:
            shortage_date = forecast_date.isoformat()
            days_until_shortage = offset

        daily_forecast.append(
            {
                "date": forecast_date.isoformat(),
                "expected_inflow": expected_inflow,
                "running_balance": running_balance,
            }
        )

    return {
        "daily_forecast": daily_forecast,
        "shortage_date": shortage_date,
        "lowest_balance": round(lowest_balance, 2),
        "days_until_shortage": days_until_shortage,
    }
