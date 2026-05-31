# -*- coding: utf-8 -*-
import httpx

from app.config import settings

TWILIO_MESSAGES_URL = (
    f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
)


def format_inr(amount: float) -> str:
    whole, _, frac = f"{amount:.2f}".partition(".")
    if len(whole) <= 3:
        formatted = whole
    else:
        last3 = whole[-3:]
        rest = whole[:-3]
        parts: list[str] = []
        while rest:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        formatted = ",".join(parts + [last3])
    return f"₹{formatted}.{frac}"


def _normalize_phone(number: str) -> str:
    phone = number.strip().replace(" ", "").replace("-", "")
    if phone.startswith("whatsapp:"):
        phone = phone[len("whatsapp:"):]
    if phone.startswith("+91"):
        return phone
    if phone.startswith("91") and len(phone) == 12:
        return f"+{phone}"
    if phone.startswith("0"):
        phone = phone[1:]
    return f"+91{phone}"


async def send_whatsapp(to_number: str, message: str) -> dict:
    to = to_number if to_number.startswith("whatsapp:") else f"whatsapp:{_normalize_phone(to_number)}"

    from_number = settings.TWILIO_WHATSAPP_FROM
    if not from_number.startswith("whatsapp:"):
        from_number = f"whatsapp:{from_number}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            TWILIO_MESSAGES_URL,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            data={"To": to, "From": from_number, "Body": message},
        )
        response.raise_for_status()
        return response.json()


def build_owner_summary(
    business_name: str,
    metrics: dict,
    top_risks: list[dict],
    insight_summary: str,
) -> str:
    risky_lines_en = []
    risky_lines_ta = []
    for index, customer in enumerate(top_risks[:3], start=1):
        name = customer.get("name") or customer.get("customer_name", "Unknown")
        amount = format_inr(float(customer.get("total_outstanding", 0)))
        days = customer.get("max_days_overdue", 0)
        risky_lines_en.append(f"{index}. {name} — {amount} ({days} days overdue)")
        risky_lines_ta.append(f"{index}. {name} — {amount} ({days} நாட்கள் தாமதம்)")

    risky_en = "\n".join(risky_lines_en) if risky_lines_en else "No risky customers this week."
    risky_ta = "\n".join(risky_lines_ta) if risky_lines_ta else "இந்த வாரம் ஆபத்தான வாடிக்கையாளர்கள் இல்லை."

    summary_text = insight_summary.strip() if insight_summary else "No AI insights generated yet."
    summary_ta = insight_summary.strip() if insight_summary else "இன்னும் AI நுண்ணறிவு உருவாக்கப்படவில்லை."

    english = (
        f"*Weekly Cash Summary — {business_name}*\n\n"
        f"Total Receivables: {format_inr(metrics['total_receivables'])}\n"
        f"Amount Collected: {format_inr(metrics['amount_collected'])}\n"
        f"Overdue Amount: {format_inr(metrics['overdue_amount'])}\n"
        f"At Risk Amount: {format_inr(metrics['at_risk_amount'])}\n\n"
        f"*Top 3 Risky Customers:*\n{risky_en}\n\n"
        f"*AI Insight:*\n{summary_text}"
    )

    tamil = (
        f"*வாராந்திர பணப்புழக்க சுருக்கம் — {business_name}*\n\n"
        f"மொத்த பெறத்தக்க தொகை: {format_inr(metrics['total_receivables'])}\n"
        f"வசூலிக்கப்பட்ட தொகை: {format_inr(metrics['amount_collected'])}\n"
        f"தாமதமான தொகை: {format_inr(metrics['overdue_amount'])}\n"
        f"ஆபத்தில் உள்ள தொகை: {format_inr(metrics['at_risk_amount'])}\n\n"
        f"*முதல் 3 ஆபத்தான வாடிக்கையாளர்கள்:*\n{risky_ta}\n\n"
        f"*AI நுண்ணறிவு:*\n{summary_ta}"
    )

    return f"{english}\n\n---\n\n{tamil}"


def build_customer_reminder(
    customer_name: str,
    business_name: str,
    invoices: list[dict],
) -> str:
    from app.services.risk_engine import get_days_overdue

    unpaid = [inv for inv in invoices if inv.get("status") != "paid"]
    unpaid_count = len(unpaid)
    total_outstanding = sum(
        float(inv.get("amount", 0)) - float(inv.get("paid_amount", 0))
        for inv in unpaid
    )
    oldest_overdue = max(
        (get_days_overdue(inv["due_date"]) for inv in unpaid if inv.get("due_date")),
        default=0,
    )

    english = (
        f"Dear {customer_name},\n\n"
        f"This is a friendly reminder from *{business_name}* regarding your outstanding payments.\n\n"
        f"Unpaid Invoices: {unpaid_count}\n"
        f"Total Outstanding: {format_inr(total_outstanding)}\n"
        f"Oldest Overdue: {oldest_overdue} days\n\n"
        f"Please arrange payment at your earliest convenience. Thank you for your continued business!"
    )

    tamil = (
        f"அன்புள்ள {customer_name},\n\n"
        f"*{business_name}* இலிருந்து உங்கள் நிலுவைத் தொகை குறித்த friendly நினைவூட்டல்.\n\n"
        f"செலுத்தப்படாத இன்வாய்ஸ்கள்: {unpaid_count}\n"
        f"மொத்த நிலுவை: {format_inr(total_outstanding)}\n"
        f"அதிக தாமதம்: {oldest_overdue} நாட்கள்\n\n"
        f"தயவுசெய்து விரைவில் பணம் செலுத்த உசவி கேட்கிறோம். உங்கள் தொடர்ச்சியான ஆதரவுக்கு நன்றி!"
    )

    return f"{english}\n\n---\n\n{tamil}"