from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer

from app.routers import auth, dashboard, forecast, insights, invoices, whatsapp

security = HTTPBearer()

app = FastAPI(
    title="CashFlow Co-Pilot",
    description="AI-powered cash flow intelligence for Tamil Nadu SMBs",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,     prefix="/auth",     tags=["auth"])
app.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
app.include_router(insights.router, prefix="/insights", tags=["insights"])
app.include_router(dashboard.router,prefix="/dashboard",tags=["dashboard"])
app.include_router(forecast.router, prefix="/forecast", tags=["forecast"])
app.include_router(whatsapp.router, prefix="/whatsapp", tags=["whatsapp"])


@app.get("/health")
async def health():
    return {"status": "ok"}