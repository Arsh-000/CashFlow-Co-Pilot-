import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
  Dot,
} from "recharts";
import { apiFetch, formatINR } from "@/lib/crest";

type DailyPoint = {
  date: string;
  expected_inflow: number;
  running_balance: number;
};

type ForecastResponse = {
  daily_forecast: DailyPoint[];
  shortage_date: string | null;
  lowest_balance: number;
  lowest_balance_date: string;
  summary: {
    starting_balance: number;
    total_expected_inflow: number;
    total_outstanding: number;
    high_risk_outstanding: number;
    total_monthly_expenses: number;
  };
};

function SummaryCard({
  label,
  value,
  bg,
  fg,
}: {
  label: string;
  value: string;
  bg: string;
  fg: string;
}) {
  return (
    <div className={`rounded-2xl border border-slate-200 p-4 ${bg}`}>
      <div className={`mb-1 text-xs font-medium ${fg} opacity-80`}>{label}</div>
      <div className={`text-xl font-bold sm:text-2xl ${fg}`}>{value}</div>
    </div>
  );
}

export function ForecastSection() {
  const [startingBalance, setStartingBalance] = useState("500000");
  const [monthlyExpenses, setMonthlyExpenses] = useState("200000");
  const [data, setData] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch("/business/settings");
        if (!res.ok) return;
        const json = await res.json();
        if (cancelled) return;
        if (json?.starting_balance != null) setStartingBalance(String(json.starting_balance));
        if (json?.monthly_expenses != null) setMonthlyExpenses(String(json.monthly_expenses));
      } catch {
        // ignore prefill errors
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    const sb = Number(startingBalance) || 0;
    const me = Number(monthlyExpenses) || 0;
    try {
      const [, res] = await Promise.all([
        apiFetch("/business/settings", {
          method: "PATCH",
          body: JSON.stringify({ starting_balance: sb, monthly_expenses: me }),
        }),
        apiFetch("/forecast/generate", {
          method: "POST",
          body: JSON.stringify({
            starting_balance: sb,
            monthly_expenses: me,
            forecast_days: 30,
          }),
        }),
      ]);
      if (!res.ok) {
        const t = await res.text();
        throw new Error(`Failed: ${res.status} - ${t}`);
      }
      const json: ForecastResponse = await res.json();
      console.log("Forecast API Response:", json);
      setData(json);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to generate forecast");
    } finally {
      setLoading(false);
    }
  }

  const chartData = data?.daily_forecast ?? [];

  return (
    <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5">
      <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-[#0f172a]">
        <span aria-hidden>📈</span> 30-Day Cash Flow Forecast
      </h2>

      <form
        onSubmit={generate}
        className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
      >
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-700">
            Starting Balance (₹)
          </label>
          <input
            type="number"
            min="0"
            value={startingBalance}
            onChange={(e) => setStartingBalance(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-[#0f172a] focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-700">
            Monthly Expenses (₹)
          </label>
          <input
            type="number"
            min="0"
            value={monthlyExpenses}
            onChange={(e) => setMonthlyExpenses(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-[#0f172a] focus:outline-none"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="h-10 rounded-lg bg-[#0f172a] px-4 text-sm font-semibold text-white transition hover:bg-[#1e293b] disabled:opacity-60"
        >
          {loading ? "Generating..." : "Generate Forecast"}
        </button>
      </form>

      {err && <p className="mb-4 text-sm text-red-600">{err}</p>}

      {loading && (
        <div className="space-y-3">
          <div className="h-64 animate-pulse rounded-lg bg-slate-100" />
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-20 animate-pulse rounded-lg bg-slate-100" />
            ))}
          </div>
        </div>
      )}

      {!loading && data && (
        <>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: "#475569" }}
                  tickFormatter={(d: string) => (d || "").slice(5)}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "#475569" }}
                  tickFormatter={(v: number) =>
                    v >= 100000 ? `${(v / 100000).toFixed(1)}L` : `${v / 1000}k`
                  }
                />
                <Tooltip
                  formatter={(value: number) => formatINR(value)}
                  labelFormatter={(l) => `Date: ${l}`}
                />
                <Line
                  type="monotone"
                  dataKey="running_balance"
                  name="Running Balance"
                  stroke="#0f172a"
                  strokeWidth={2}
                  dot={(props: {
                    cx?: number;
                    cy?: number;
                    payload?: DailyPoint;
                    index?: number;
                  }) => {
                    const { cx, cy, payload, index } = props;
                    if (
                      typeof cx !== "number" ||
                      typeof cy !== "number" ||
                      !payload
                    ) {
                      return <g key={`d-${index ?? 0}`} />;
                    }
                    if (payload.expected_inflow > 0) {
                      return (
                        <Dot
                          key={`d-${index ?? payload.date}`}
                          cx={cx}
                          cy={cy}
                          r={4}
                          fill="#10b981"
                          stroke="#065f46"
                          strokeWidth={1}
                        />
                      );
                    }
                    return <g key={`d-${index ?? payload.date}`} />;
                  }}
                  activeDot={{ r: 5 }}
                />
                {data.shortage_date && (
                  <ReferenceLine
                    x={data.shortage_date}
                    stroke="#dc2626"
                    strokeWidth={2}
                    label={{
                      value: "Cash Shortage",
                      position: "top",
                      fill: "#dc2626",
                      fontSize: 12,
                      fontWeight: 600,
                    }}
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <SummaryCard
              label="Starting Balance"
              value={formatINR(data.summary.starting_balance)}
              bg="bg-slate-100"
              fg="text-[#0f172a]"
            />
            <SummaryCard
              label="Expected Collections"
              value={formatINR(data.summary.total_expected_inflow)}
              bg="bg-emerald-100"
              fg="text-emerald-900"
            />
            <SummaryCard
              label="High Risk Amount"
              value={formatINR(data.summary.high_risk_outstanding)}
              bg="bg-red-100"
              fg="text-red-900"
            />
            <SummaryCard
              label="Lowest Balance"
              value={formatINR(data.lowest_balance)}
              bg="bg-amber-100"
              fg="text-amber-900"
            />
          </div>
          <p className="mt-3 text-sm text-slate-600">
            Lowest point: <span className="font-medium">{data.lowest_balance_date}</span>
          </p>
        </>
      )}

      {!loading && !data && !err && (
        <p className="text-sm text-slate-500">
          Enter your starting balance and monthly expenses, then generate a 30-day forecast.
        </p>
      )}
    </section>
  );
}
