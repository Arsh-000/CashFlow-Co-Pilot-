from collections import defaultdict
from datetime import date, datetime, timedelta

# How many days after due date each risk tier is expected to pay
RISK_DELAY_DAYS = {
    "green": 7,    # Good payers — pay within a week of due date
    "amber": 21,   # Moderate — pay ~3 weeks late
    "red": 45,     # High risk — pay ~6 weeks late
}
DEFAULT_DELAY_DAYS = 15


def _parse_date(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def compute_cash_forecast(
    invoices: list[dict],
    customer_risk_levels: dict[str, str],  # {customer_id: "red"/"amber"/"green"}
    starting_balance: float,
    forecast_days: int = 30,
    daily_expense: float = 0.0,
) -> dict:
    today = date.today()
    forecast_end = today + timedelta(days=forecast_days)
    inflows_by_date: dict[date, float] = defaultdict(float)

    total_outstanding = 0.0
    high_risk_outstanding = 0.0

    for invoice in invoices:
        status = invoice.get("status", "unpaid")
        if status == "paid":
            continue

        amount = float(invoice.get("amount", 0))
        paid_amount = float(invoice.get("paid_amount", 0))
        outstanding = amount - paid_amount
        if outstanding <= 0:
            continue

        due_date_str = invoice.get("due_date")
        if not due_date_str:
            continue

        due_date = _parse_date(due_date_str)
        customer_id = invoice.get("customer_id")
        risk_level = customer_risk_levels.get(customer_id, "amber").lower()
        delay_days = RISK_DELAY_DAYS.get(risk_level, DEFAULT_DELAY_DAYS)

        total_outstanding += outstanding
        if risk_level == "red":
            high_risk_outstanding += outstanding

        # Key fix: if invoice is already overdue, predict from TODAY
        # not from due_date + delay (which gives dates 400+ days in future)
        if due_date < today:
            expected_payment_date = today + timedelta(days=delay_days)
        else:
            expected_payment_date = due_date + timedelta(days=delay_days)

        # Only include if it falls within the forecast window
        if today <= expected_payment_date <= forecast_end:
            inflows_by_date[expected_payment_date] += outstanding

    # Build daily forecast
    daily_forecast = []
    running_balance = starting_balance
    lowest_balance = starting_balance
    lowest_balance_date = today.isoformat()
    shortage_date = None
    days_until_shortage = None
    total_expected_inflow = round(sum(inflows_by_date.values()), 2)

    for offset in range(forecast_days + 1):
        forecast_date = today + timedelta(days=offset)
        expected_inflow = round(inflows_by_date.get(forecast_date, 0.0), 2)
        running_balance = round(running_balance + expected_inflow - daily_expense, 2)

        if running_balance < lowest_balance:
            lowest_balance = running_balance
            lowest_balance_date = forecast_date.isoformat()

        if shortage_date is None and running_balance < 0:
            shortage_date = forecast_date.isoformat()
            days_until_shortage = offset

        daily_forecast.append({
            "date": forecast_date.isoformat(),
            "expected_inflow": expected_inflow,
            "running_balance": running_balance,
        })

    return {
        "daily_forecast": daily_forecast,
        "shortage_date": shortage_date,
        "days_until_shortage": days_until_shortage,
        "lowest_balance": round(lowest_balance, 2),
        "lowest_balance_date": lowest_balance_date,
        "summary": {
            "starting_balance": round(starting_balance, 2),
            "total_expected_inflow": total_expected_inflow,
            "total_outstanding": round(total_outstanding, 2),
            "high_risk_outstanding": round(high_risk_outstanding, 2),
            "total_monthly_expenses": round(daily_expense * 30, 2),
        },
    }