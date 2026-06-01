# -*- coding: utf-8 -*-
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import supabase
from app.services.forecast_engine import compute_cash_forecast
from app.services.risk_engine import compute_customer_summaries, compute_metrics
from app.services.whatsapp_service import (
    build_customer_reminder,
    build_owner_summary,
    send_whatsapp,
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


def _fetch_all_businesses() -> list[dict]:
    response = (
        supabase.table("businesses")
        .select("id, name, phone, starting_balance, monthly_expenses")
        .execute()
    )
    return response.data or []


def _fetch_invoices_for_business(business_id: str) -> list[dict]:
    response = (
        supabase.table("invoices")
        .select("*, customers(name, phone, risk_level)")
        .eq("business_id", business_id)
        .execute()
    )
    invoices = []
    for row in response.data or []:
        customer = row.get("customers") or {}
        invoices.append({
            **row,
            "customer_name": customer.get("name"),
            "customer_phone": customer.get("phone"),
            "customer_risk_level": customer.get("risk_level"),
        })
    return invoices


def _fetch_customers_for_business(business_id: str) -> list[dict]:
    response = (
        supabase.table("customers")
        .select("id, name, phone, risk_level")
        .eq("business_id", business_id)
        .execute()
    )
    return response.data or []


def _fetch_latest_insight(business_id: str) -> str:
    response = (
        supabase.table("insights")
        .select("summary")
        .eq("business_id", business_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if response.data:
        return response.data[0].get("summary") or ""
    return ""


async def job_daily_reminders():
    """Daily 9am IST — send payment reminders to all customers with unpaid invoices."""
    logger.info("Running daily reminders job")
    businesses = _fetch_all_businesses()

    for business in businesses:
        business_id = business["id"]
        business_name = business["name"]

        try:
            customers = _fetch_customers_for_business(business_id)
            customers_with_phone = [c for c in customers if c.get("phone")]

            if not customers_with_phone:
                continue

            invoices = _fetch_invoices_for_business(business_id)

            for customer in customers_with_phone:
                customer_invoices = [
                    inv for inv in invoices
                    if inv.get("customer_id") == customer["id"]
                ]
                if not any(inv.get("status") != "paid" for inv in customer_invoices):
                    continue

                message = build_customer_reminder(
                    customer_name=customer["name"],
                    business_name=business_name,
                    invoices=customer_invoices,
                )
                await send_whatsapp(customer["phone"], message)
                logger.info(f"Reminder sent to {customer['name']} ({customer['phone']})")

        except Exception as e:
            logger.error(f"Error sending reminders for business {business_id}: {e}")


async def job_weekly_owner_summary():
    """Monday 9am IST — send weekly summary to all business owners."""
    logger.info("Running weekly owner summary job")
    businesses = _fetch_all_businesses()

    for business in businesses:
        business_id = business["id"]

        if not business.get("phone"):
            continue

        try:
            invoices = _fetch_invoices_for_business(business_id)
            metrics = compute_metrics(invoices)
            customer_summaries = compute_customer_summaries(invoices)
            top_risks = [
                c for c in customer_summaries
                if c.get("risk_level") in ("Red", "Amber")
            ][:3]
            insight_summary = _fetch_latest_insight(business_id)

            # Compute forecast
            starting_balance = float(business.get("starting_balance") or 0)
            monthly_expenses = float(business.get("monthly_expenses") or 0)
            customers = _fetch_customers_for_business(business_id)
            customer_risk_levels = {
                c["id"]: (c.get("risk_level") or "amber").lower()
                for c in customers
            }
            forecast = compute_cash_forecast(
                invoices=invoices,
                customer_risk_levels=customer_risk_levels,
                starting_balance=starting_balance,
                forecast_days=30,
                daily_expense=monthly_expenses / 30,
            )

            message = build_owner_summary(
                business_name=business["name"],
                metrics=metrics,
                top_risks=top_risks,
                insight_summary=insight_summary,
                forecast=forecast,
            )
            await send_whatsapp(business["phone"], message)
            logger.info(f"Weekly summary sent to {business['name']} ({business['phone']})")

        except Exception as e:
            logger.error(f"Error sending weekly summary for business {business_id}: {e}")


def start_scheduler():
    # Daily reminders — 9am IST every day
    scheduler.add_job(
        job_daily_reminders,
        CronTrigger(hour=9, minute=0, timezone="Asia/Kolkata"),
        id="daily_reminders",
        replace_existing=True,
    )

    # Weekly owner summary — Monday 9am IST
    scheduler.add_job(
        job_weekly_owner_summary,
        CronTrigger(day_of_week="mon", hour=9, minute=0, timezone="Asia/Kolkata"),
        id="weekly_owner_summary",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started — daily reminders at 9am IST, weekly summary on Mondays 9am IST")