# -*- coding: utf-8 -*-
import base64
import json
import re

import httpx

from app.config import settings

GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

EXTRACTION_PROMPT = """You are an invoice data extraction assistant for Indian SMBs.
Extract ALL invoice details from this image into a JSON array.

Each invoice must have these fields:
- customer_name: string (company or person name, in English if Tamil text present)
- phone: string (10-digit mobile number, empty string if not found)
- invoice_number: string (invoice/bill number, empty string if not found)
- invoice_date: string (YYYY-MM-DD format, empty string if not found)
- due_date: string (YYYY-MM-DD format, empty string if not found)
- amount: number (total invoice amount in rupees, 0 if not found)
- paid_amount: number (amount already paid, 0 if not found)
- status: string (exactly "paid", "unpaid", or "partial")

Rules:
- Return ONLY a valid JSON array, no other text, no markdown, no explanation
- If multiple invoices are visible, return all of them
- For status: if fully paid use "paid", if partially paid use "partial", otherwise "unpaid"
- Convert any date format to YYYY-MM-DD
- Remove Rs/₹ symbols from amounts, return pure numbers
- If a field is truly not visible, use empty string or 0

Example output:
[{"customer_name":"Selvam Textiles","phone":"9876543210","invoice_number":"INV-001","invoice_date":"2025-01-15","due_date":"2025-02-15","amount":185000,"paid_amount":0,"status":"unpaid"}]"""


async def extract_invoices_from_image(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
) -> list[dict]:
    """Send image to Groq vision model and extract invoice data."""

    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    image_url = f"data:{media_type};base64,{base64_image}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_VISION_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": EXTRACTION_PROMPT,
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url},
                            },
                        ],
                    }
                ],
                "max_tokens": 1000,
                "temperature": 0.1,
            },
        )
        data = response.json()

    if "choices" not in data:
        raise ValueError(f"Groq API error: {data.get('error', {}).get('message', 'Unknown error')}")

    raw = data["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences if present
    raw = re.sub(r"```json|```", "", raw).strip()

    try:
        extracted = json.loads(raw)
        if isinstance(extracted, dict):
            extracted = [extracted]
        return extracted
    except json.JSONDecodeError:
        raise ValueError(f"Could not parse extracted data as JSON: {raw[:200]}")