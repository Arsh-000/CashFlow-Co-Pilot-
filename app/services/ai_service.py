import json
import re

import httpx

from app.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are a cash flow advisor for a small business in Tamil Nadu India. "
    "Analyse the invoice data and respond with exactly these four sections: "
    "SUMMARY, TOP 3 RISKY CUSTOMERS, URGENT ACTION, TAMIL SUMMARY. "
    "Do not use any markdown formatting. Do not use ## or ** or * symbols anywhere in your response. Write in plain text only."
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