import json
import re

import anthropic

from app.config import settings

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

SYSTEM_PROMPT = (
    "You are a cash flow advisor for a small business in Tamil Nadu India. "
    "Analyse the invoice data and respond with exactly these four sections: "
    "SUMMARY, TOP 3 RISKY CUSTOMERS, URGENT ACTION, TAMIL SUMMARY."
)


def generate_insights(invoices: list[dict], metrics: dict) -> str:
    prompt = (
        f"Invoice data:\n{json.dumps(invoices, indent=2, default=str)}\n\n"
        f"Metrics:\n{json.dumps(metrics, indent=2)}\n\n"
        "Provide your analysis in the four required sections."
    )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def parse_insight_sections(text: str) -> dict:
    patterns = {
        "summary": r"SUMMARY[:\s]*(.+?)(?=TOP 3 RISKY CUSTOMERS|$)",
        "top_risks": r"TOP 3 RISKY CUSTOMERS[:\s]*(.+?)(?=URGENT ACTION|$)",
        "urgent_action": r"URGENT ACTION[:\s]*(.+?)(?=TAMIL SUMMARY|$)",
        "tamil_summary": r"TAMIL SUMMARY[:\s]*(.+?)$",
    }

    result = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            content = match.group(1).strip()
            if key == "top_risks":
                lines = [line.strip().lstrip("-•0123456789.) ") for line in content.split("\n") if line.strip()]
                result[key] = [line for line in lines if line]
            else:
                result[key] = content
        else:
            result[key] = [] if key == "top_risks" else ""

    return result
