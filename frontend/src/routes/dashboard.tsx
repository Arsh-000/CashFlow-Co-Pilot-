import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { MessageCircle } from "lucide-react";
import { CrestNav } from "@/components/CrestNav";
import { ForecastSection } from "@/components/ForecastSection";
import { apiFetch, formatINR, getToken } from "@/lib/crest";

export const Route = createFileRoute("/dashboard")({
  head: () => ({ meta: [{ title: "Dashboard — Crest" }] }),
  component: DashboardPage,
});

type Summary = {
  metrics?: {
    total_receivables?: number;
    amount_collected?: number;
    overdue_amount?: number;
    at_risk_amount?: number;
  };
  customers?: Array<{
    customer_name?: string;
    name?: string;
    total_outstanding?: number;
    outstanding_amount?: number;
    max_days_overdue?: number;
    days_overdue?: number;
    risk_level?: string;
    risk?: string;
  }>;
  invoices?: Array<{
    customer_name?: string;
    customers?: { name?: string };
    invoice_number?: string;
    due_date?: string;
    amount?: number;
    paid_amount?: number;
    status?: string;
  }>;
  latest_insight?: unknown;
};


function Spinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-[#0f172a]" />
    </div>
  );
}

function WhatsappActionsSection() {
  const [busy, setBusy] = useState(false);

  async function sendReminders() {
    setBusy(true);
    try {
      const res = await apiFetch("/whatsapp/send-reminders", { method: "POST" });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Failed: ${res.status}`);
      }
      const result = await res.json();
      toast.success(`Reminders sent to ${result?.sent ?? 0} customers`);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to send reminders");
    } finally {
      setBusy(false);
    }
  }

  async function sendOwnerSummary() {
    setBusy(true);
    try {
      const res = await apiFetch("/whatsapp/send-owner-summary", { method: "POST" });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Failed: ${res.status}`);
      }
      toast.success("Weekly summary sent successfully");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to send summary");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5">
      <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-[#0f172a]">
        <MessageCircle className="h-5 w-5" color="#25D366" />
        WhatsApp Actions
      </h2>
      <div className="flex flex-wrap gap-3">
        <button
          onClick={sendReminders}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-lg border border-[#25D366] bg-white px-4 py-2.5 text-sm font-semibold text-[#25D366] transition hover:bg-[#25D366]/10 disabled:opacity-60"
        >
          {busy && (
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-[#25D366] border-t-transparent" />
          )}
          Send Payment Reminders
        </button>
        <button
          onClick={sendOwnerSummary}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-lg border border-[#25D366] bg-white px-4 py-2.5 text-sm font-semibold text-[#25D366] transition hover:bg-[#25D366]/10 disabled:opacity-60"
        >
          {busy && (
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-[#25D366] border-t-transparent" />
          )}
          Send Weekly Summary to Owner
        </button>
      </div>
    </section>
  );
}

function RiskBadge({ risk }: { risk: string }) {
  const r = (risk || "").toLowerCase();
  let cls = "bg-emerald-100 text-emerald-800";
  let label = risk || "On Track";
  if (r.includes("red") || r.includes("high")) {
    cls = "bg-red-100 text-red-800";
    label = "High Risk";
  } else if (r.includes("amber") || r.includes("watch") || r.includes("medium")) {
    cls = "bg-amber-100 text-amber-800";
    label = "Watch";
  } else if (r.includes("green")) {
    cls = "bg-emerald-100 text-emerald-800";
    label = "On Track";
  }
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${cls}`}>
      {label}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const s = (status || "").toLowerCase();
  let cls = "bg-red-100 text-red-800";
  let label = status || "unpaid";
  if (s === "paid") {
    cls = "bg-emerald-100 text-emerald-800";
    label = "Paid";
  } else if (s === "partial") {
    cls = "bg-amber-100 text-amber-800";
    label = "Partial";
  } else {
    label = "Unpaid";
  }
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${cls}`}>
      {label}
    </span>
  );
}

function MetricCard({
  label,
  value,
  icon,
  bg,
  fg,
}: {
  label: string;
  value: string;
  icon: string;
  bg: string;
  fg: string;
}) {
  return (
    <div className={`rounded-2xl border border-slate-200 p-5 ${bg}`}>
      <div className={`mb-2 flex items-center gap-2 text-sm font-medium ${fg}`}>
        <span aria-hidden>{icon}</span>
        <span>{label}</span>
      </div>
      <div className={`text-2xl font-bold sm:text-3xl ${fg}`}>{value}</div>
    </div>
  );
}

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function DashboardPage() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      navigate({ to: "/login" });
      return;
    }
    (async () => {
      try {
        const res = await apiFetch("/dashboard/summary");
        if (res.status === 401) {
          navigate({ to: "/login" });
          return;
        }
        if (!res.ok) throw new Error("Failed to load dashboard");
        const data = await res.json();
        setSummary(data);
      } catch (e: unknown) {
        setErr(getErrorMessage(e, "Failed to load"));
      } finally {
        setLoading(false);
      }
    })();
  }, [navigate]);


  const metrics = {
    total_receivables: Number(summary?.metrics?.total_receivables ?? 0),
    amount_collected: Number(summary?.metrics?.amount_collected ?? 0),
    overdue_amount: Number(summary?.metrics?.overdue_amount ?? 0),
    at_risk_amount: Number(summary?.metrics?.at_risk_amount ?? 0),
  };
  const riskRows = summary?.customers || [];
  const invoices = Array.from(
    new Map(
      (summary?.invoices || []).map((inv) => [
        inv.invoice_number ?? Math.random().toString(),
        { ...inv, paid_amount: Number(inv.paid_amount ?? 0) },
      ]),
    ).values(),
  );

  return (
    <div className="min-h-screen bg-white">
      <CrestNav />
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
        {loading ? (
          <Spinner />
        ) : err ? (
          <p className="text-sm text-red-600">{err}</p>
        ) : (
          <>
            <h1 className="mb-6 text-2xl font-bold text-[#0f172a]">Dashboard</h1>

            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <MetricCard
                label="Total Receivables"
                value={formatINR(metrics.total_receivables)}
                icon="₹"
                bg="bg-slate-100"
                fg="text-[#0f172a]"
              />
              <MetricCard
                label="Amount Collected"
                value={formatINR(metrics.amount_collected)}
                icon="✓"
                bg="bg-emerald-100"
                fg="text-emerald-900"
              />
              <MetricCard
                label="Overdue Amount"
                value={formatINR(metrics.overdue_amount)}
                icon="⚠"
                bg="bg-red-100"
                fg="text-red-900"
              />
              <MetricCard
                label="At Risk Amount"
                value={formatINR(metrics.at_risk_amount)}
                icon="⏱"
                bg="bg-amber-100"
                fg="text-amber-900"
              />
            </div>

            <ForecastSection />

            <WhatsappActionsSection />

            <section className="mt-8 rounded-2xl border border-slate-200 bg-white">
              <h2 className="border-b border-slate-200 px-5 py-4 text-lg font-semibold text-[#0f172a]">
                Customer Risk Summary
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-slate-600">
                    <tr>
                      <th className="px-5 py-3 font-medium">Customer Name</th>
                      <th className="px-5 py-3 font-medium">Total Outstanding</th>
                      <th className="px-5 py-3 font-medium">Days Overdue</th>
                      <th className="px-5 py-3 font-medium">Risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {riskRows.length === 0 && (
                      <tr>
                        <td colSpan={4} className="px-5 py-6 text-center text-slate-500">
                          No data
                        </td>
                      </tr>
                    )}
                    {riskRows.map((r, i) => (
                      <tr key={i} className="border-t border-slate-100 hover:bg-slate-50">
                        <td className="px-5 py-3 font-medium text-[#0f172a]">
                          {r.customer_name || r.name || "—"}
                        </td>
                        <td className="px-5 py-3">
                          {formatINR(r.total_outstanding ?? r.outstanding_amount)}
                        </td>
                        <td className="px-5 py-3">{r.max_days_overdue ?? r.days_overdue ?? 0}</td>
                        <td className="px-5 py-3">
                          <RiskBadge risk={r.risk_level || r.risk || ""} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>


            <section className="mt-8 rounded-2xl border border-slate-200 bg-white">
              <h2 className="border-b border-slate-200 px-5 py-4 text-lg font-semibold text-[#0f172a]">
                All Invoices
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-slate-600">
                    <tr>
                      <th className="px-5 py-3 font-medium">Customer</th>
                      <th className="px-5 py-3 font-medium">Invoice Number</th>
                      <th className="px-5 py-3 font-medium">Due Date</th>
                      <th className="px-5 py-3 font-medium">Amount</th>
                      <th className="px-5 py-3 font-medium">Paid</th>
                      <th className="px-5 py-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-5 py-6 text-center text-slate-500">
                          No invoices
                        </td>
                      </tr>
                    )}
                    {invoices.map((inv, i) => (
                      <tr key={i} className="border-t border-slate-100 hover:bg-slate-50">
                        <td className="px-5 py-3 font-medium text-[#0f172a]">
                          {inv.customer_name || inv.customers?.name || "—"}
                        </td>
                        <td className="px-5 py-3">{inv.invoice_number || "—"}</td>
                        <td className="px-5 py-3">{inv.due_date || "—"}</td>
                        <td className="px-5 py-3">{formatINR(inv.amount)}</td>
                        <td className="px-5 py-3">{formatINR(inv.paid_amount)}</td>
                        <td className="px-5 py-3">
                          <StatusBadge status={inv.status || "unpaid"} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

