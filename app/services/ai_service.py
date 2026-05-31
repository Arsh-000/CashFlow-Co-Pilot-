import json
import re

import httpx

from app.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are a cash flow advisor for a small business in Tamil Nadu India. "
    "Analyse the invoice data and respond with exactly these four sections. "
    "Do not use markdown formatting. Do not use ## or ** or * symbols. Write in plain text only. "
    "Format all amounts in Indian rupee format with the rupee symbol like Rs 12,15,000 not 1215000.0. "
    "\n\n"
    "SUMMARY\n"
    "Write exactly 2 short sentences about the overall cash position. Be specific with rupee amounts.\n"
    "\n"
    "TOP 3 RISKY CUSTOMERS\n"
    "List exactly 3 customers as numbered points like this:\n"
    "1. Customer name - amount overdue and number of days overdue\n"
    "2. Customer name - amount overdue and number of days overdue\n"
    "3. Customer name - amount overdue and number of days overdue\n"
    "\n"
    "URGENT ACTION\n"
    "Write exactly 1 sentence. Name the specific customer and amount. Tell the owner exactly what to do today.\n"
    "\n"
    "TAMIL SUMMARY\n"
    "Translate only the SUMMARY section into Tamil. Write 2 sentences."
)


def generate_insights(invoices: list[dict], metrics: dict) -> str:
    prompt = (
        f"Invoice data:\n{json.dumps(invoices, indent=2, default=str)}\n\n"
        f"Metrics:\n{json.dumps(metrics, indent=2)}\n\n"
        "Provide your analysis in the four required sections."
    )

    response = httpx.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "max_tokens": 1000,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


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