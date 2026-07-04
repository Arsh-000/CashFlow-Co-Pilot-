# CLAUDE.md — Crest AI Cash Flow Platform

## Project overview
Crest is an AI-powered cash flow intelligence platform for Tamil Nadu SMBs (textile traders, auto component manufacturers, FMCG distributors). It ingests invoices via CSV or image OCR, scores customer payment risk, generates 30-day cash flow forecasts, sends bilingual WhatsApp reminders, and answers natural language questions about business finances via Groq LLM. Tagline: "Your business at its peak" / "உங்கள் வணிகம் உச்சத்தில்"

## Live URLs
- **Backend:** https://web-production-12233.up.railway.app
- **Frontend:** https://crest-cashflow-peak.lovable.app
- **Swagger docs:** https://web-production-12233.up.railway.app/docs
- **Repo:** https://github.com/Arsh-000/CashFlow-Co-Pilot-

## Architecture
```
React Frontend (Lovable/PWA)
        ↓ Bearer token (localStorage: "crest_token")
FastAPI Backend (Railway, Singapore)
        ↓
Supabase PostgreSQL (Singapore, project: ykfisaajudgxwxmmlian)
        ↓
Groq API (LLM text + vision) | Twilio (WhatsApp)
```

## Tech stack
- **Backend:** Python 3.13.13, FastAPI 0.136.3, Uvicorn, uv
- **Database:** Supabase PostgreSQL, Singapore region
- **Auth:** Supabase Auth (legacy JWT keys — eyJ format)
- **AI/LLM:** Groq — llama-3.3-70b-versatile (text), meta-llama/llama-4-scout-17b-16e-instruct (vision)
- **WhatsApp:** Twilio sandbox (+14155238886, join: "join move-trace")
- **Scheduler:** APScheduler 3.11.2 (AsyncIOScheduler, Asia/Kolkata)
- **HTTP client:** httpx for ALL DB writes and external calls
- **Frontend:** React + Tailwind + TanStack Router (Lovable prototype)
- **Hosting:** Railway (Singapore) + Lovable

## Key directories
```
app/main.py                    — FastAPI app, CORS, routers, scheduler lifespan
app/config.py                  — Pydantic Settings (env vars)
app/database.py                — Supabase client + httpx helpers
app/scheduler.py               — Daily 9am IST reminders + Monday 9am IST owner summary
app/middleware/auth_middleware.py — JWT verify + business_id lookup (10min cache)
app/routers/auth.py            — POST /auth/signup, POST /auth/login
app/routers/invoices.py        — CSV upload, image OCR upload, list, mark-paid, payment history
app/routers/dashboard.py       — GET /dashboard/summary
app/routers/insights.py        — generate, latest, chat
app/routers/forecast.py        — POST /forecast/generate
app/routers/whatsapp.py        — send-reminders, send-owner-summary, test
app/routers/business.py        — settings, profile, account, password, export, delete
app/services/ai_service.py     — Groq text completion
app/services/ocr_service.py    — Groq vision invoice extraction
app/services/risk_engine.py    — Red/Amber/Green scoring
app/services/forecast_engine.py — 30-day cash flow computation
app/services/whatsapp_service.py — Twilio + bilingual message builders
frontend/src/routes/           — All page components
frontend/src/components/       — CrestShell, CrestLogo, AuthCard, etc.
frontend/src/lib/crest.ts      — API client (apiFetch, getToken, setToken, clearToken)
```

## Commands
```bash
# Install backend
uv sync

# Run backend locally
uvicorn app.main:app --reload --port 8000

# Run frontend locally
cd frontend && npm install && npm run dev

# Deploy (auto-triggers Railway deploy)
git add . && git commit -m "message" && git push origin main
```

## Database schema

### businesses
| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| owner_id | uuid FK | → auth.users.id |
| name | text | Business name |
| city | text | |
| phone | text | 10 digits, no +91 |
| language | text | "en_ta" or "en", DEFAULT "en_ta" |
| starting_balance | float8 | For forecast |
| monthly_expenses | float8 | For forecast |
| created_at | timestamptz | |

### customers
| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| business_id | uuid FK | → businesses.id |
| name | text | |
| phone | text | 10 digits, no +91 |
| risk_level | text | "red" / "amber" / "green" (lowercase) |
| created_at | timestamptz | |

### invoices
| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| business_id | uuid FK | |
| customer_id | uuid FK | → customers.id |
| invoice_number | text | Used for dedup |
| invoice_date | date | YYYY-MM-DD |
| due_date | date | YYYY-MM-DD |
| amount | float8 | Total invoice amount in rupees |
| paid_amount | float8 | Amount paid so far |
| status | text | "unpaid" / "partial" / "paid" |
| payment_date | date | Set when mark-paid called |
| created_at | timestamptz | |

### insights
| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| business_id | uuid FK | |
| summary | text | English AI summary |
| top_risks | jsonb | Array of {name, total_outstanding, max_days_overdue} |
| urgent_action | text | English action item |
| tamil_summary | text | Tamil translation |
| raw_response | text | Full Groq response |
| created_at | timestamptz | |

### payment_events
| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| invoice_id | uuid FK | → invoices.id, CASCADE DELETE |
| business_id | uuid FK | |
| customer_id | uuid FK | |
| payment_date | date | Actual date payment received |
| amount_paid | float8 | Amount in this payment event |
| days_from_due_date | int | Positive=late, negative=early. Core ML training signal. |
| created_at | timestamptz | |

## API endpoints

### Auth (no auth required)
| Method | Path | Body | Response |
|---|---|---|---|
| POST | /auth/signup | {email, password, business_name, city, phone} | {access_token} |
| POST | /auth/login | {email, password} | {access_token} |

### Invoices (Bearer required)
| Method | Path | Notes |
|---|---|---|
| POST | /invoices/upload/csv | Multipart CSV. Returns {inserted, skipped} |
| POST | /invoices/upload/image | Multipart image JPEG/PNG/WEBP max 10MB. Returns {inserted, skipped, extracted_data} |
| POST | /invoices/{id}/mark-paid | Body: {amount_paid, payment_date?}. Writes payment_event |
| GET | /invoices/list | Params: ?search=, ?status=, ?customer_id= |
| GET | /invoices/customers/{id}/payment-history | Returns avg_days_from_due, payment_events array |

### Dashboard (Bearer required)
| Method | Path | Response |
|---|---|---|
| GET | /dashboard/summary | {metrics, customers, invoices, latest_insight} |

### Insights (Bearer required)
| Method | Path | Notes |
|---|---|---|
| POST | /insights/generate | Generates via Groq, stores in DB |
| GET | /insights/latest | Most recent insight |
| POST | /insights/chat | Body: {question} → {answer} |

### Forecast (Bearer required)
| Method | Path | Notes |
|---|---|---|
| POST | /forecast/generate | Body: {starting_balance, monthly_expenses, forecast_days?} |

### WhatsApp (Bearer required)
| Method | Path | Notes |
|---|---|---|
| POST | /whatsapp/send-reminders | Sends to all customers with unpaid invoices + phone |
| POST | /whatsapp/send-owner-summary | Sends weekly summary to owner phone |
| POST | /whatsapp/test | Body: {to, message} |

### Business (Bearer required)
| Method | Path | Notes |
|---|---|---|
| GET | /business/settings | Returns {id, name, city, phone, language, starting_balance, monthly_expenses} |
| PATCH | /business/settings | Body: {starting_balance, monthly_expenses} |
| PATCH | /business/profile | Body: {name?, city?, phone?, language?} |
| GET | /business/account | Returns {user_id, email, created_at} |
| PATCH | /business/account/password | Body: {new_password} min 8 chars |
| GET | /business/export | Returns all tables as JSON (DPDP compliance) |
| DELETE | /business/account | Deletes all data + auth user. Irreversible. |

### Health
| Method | Path |
|---|---|
| GET | /health |

## Environment variables
| Name | Purpose | Required |
|---|---|---|
| SUPABASE_URL | Supabase project URL | ✅ |
| SUPABASE_ANON_KEY | Legacy anon JWT (eyJ...) | ✅ |
| SUPABASE_SERVICE_KEY | Legacy service role JWT — all DB writes | ✅ |
| GROQ_API_KEY | Groq API for LLM + vision | ✅ |
| SECRET_KEY | App secret key | ✅ |
| ENVIRONMENT | "development" or "production" | ✅ |
| TWILIO_ACCOUNT_SID | Twilio Account SID | ✅ |
| TWILIO_AUTH_TOKEN | Twilio Auth Token | ✅ |
| TWILIO_WHATSAPP_FROM | whatsapp:+14155238886 (sandbox) | ✅ |

## Conventions — MUST follow

1. **ALL DB writes → httpx PATCH/POST to Supabase REST API directly** — never `supabase.table().update()` or `.upsert()` — they throw AttributeError
2. **Every DB query filters by business_id** — no exceptions
3. **Auth middleware returns {user_id, business_id, token}** — token needed for Supabase Auth calls
4. **Phone numbers stored as 10 digits, no +91** — Twilio adds +91 prefix when sending
5. **Dates always YYYY-MM-DD** — never DD/MM/YYYY
6. **Tamil text files** need `# -*- coding: utf-8 -*-` as first line
7. **Token stored in localStorage as "crest_token"** — cleared on 401
8. **Frontend API calls via apiFetch()** from src/lib/crest.ts — never raw fetch
9. **Deploy by pushing to main** — Railway auto-deploys in ~60 seconds
10. **Risk levels always lowercase** — "red", "amber", "green" — never "Red", "Amber", "Green"

## NEVER do
- Never use `supabase.table().update()` or `.upsert()` — use httpx PATCH
- Never remove the `business_id` filter from any DB query
- Never store phone numbers with +91 prefix in DB
- Never commit `.env` — use `.env.example` with placeholder names
- Never use `Bearer Bearer token` — Swagger adds Bearer prefix automatically
- Never send customer phone numbers to Groq API

## Scheduler (runs automatically)
- **Daily 9am IST** — sends payment reminders to all customers with unpaid invoices across all businesses
- **Monday 9am IST** — sends owner weekly summary (metrics + forecast + AI insight) to all business owner phones
- Implemented in `app/scheduler.py` using APScheduler, started via FastAPI lifespan

## Frontend integration notes
- `CrestShell.tsx` fetches business name/city from `GET /business/settings` (not dashboard/summary)
- Dashboard insight fields: backend sends `summary` (not `body`) and `created_at` (not `generated_at`)
- Invoice list now returns `risk_level` from customers join — use this to compute Overdue vs At-Risk display status
- `payment_events` → `GET /invoices/customers/{id}/payment-history` → real avg_days_from_due for Trust Score
- WhatsApp toggles on dashboard call `POST /whatsapp/send-reminders` and `POST /whatsapp/send-owner-summary`
- Avatar in header links to `/settings` on mobile (only way to reach settings on mobile)

## Test accounts
- arsh.box1804@gmail.com / arsh1234 (main, has invoice data)
- karthik@coimbatore.com / Test@1234 (empty)

## Known gotchas
- supabase-py `.update()` and `.upsert()` throw AttributeError — always use httpx
- Twilio sandbox: recipients must send "join move-trace" to +14155238886, sessions expire 72h
- Railway env vars: no trailing newlines — causes httpx.InvalidURL
- Auth cache TTL is 10 minutes — user changes are reflected after cache expires
- RLS policies already exist — don't run CREATE POLICY again (error 42710)
- `language` column added to businesses table — required for profile endpoints

## External services
| Service | Purpose | Config |
|---|---|---|
| Supabase | PostgreSQL + Auth | SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY |
| Groq | LLM text + vision OCR | GROQ_API_KEY |
| Twilio | WhatsApp sandbox | TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM |
| Railway | Backend hosting, Singapore | Auto-deploy on git push to main |
| Lovable | Frontend prototype | crest-cashflow-peak.lovable.app |

## Open backlog (priority order)
1. Rate limiting on auth endpoints
2. Sentry error tracking + observability
3. Two-way WhatsApp webhook
4. Real WhatsApp Business API (Interakt/AiSensy)
5. Learned payment delays from payment_events (needs 3+ months real data)
6. Next.js 15 frontend rewrite (12 Cursor prompts ready — ask for them)
7. Tally/Busy ERP integration
8. UPI payment links (Razorpay/Cashfree)
9. Multi-user/roles

## Glossary
| Term | Meaning |
|---|---|
| business_id | UUID of the business — primary data isolation unit |
| risk_level | "red" (31+ days overdue), "amber" (1-30 days), "green" (0 days) |
| days_from_due_date | In payment_events: positive=late, negative=early. Core ML signal. |
| payment_events | Append-only payment log — the ML training data pipeline |
| en_ta | Language setting: English + Tamil (bilingual WhatsApp messages) |
| InkYank | Studio name associated with the developer (Arsh) |
