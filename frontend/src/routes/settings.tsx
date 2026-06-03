import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Settings, Loader2 } from "lucide-react";
import { CrestNav } from "@/components/CrestNav";
import { apiFetch, getToken } from "@/lib/crest";

export const Route = createFileRoute("/settings")({
  head: () => ({ meta: [{ title: "Settings — Crest" }] }),
  component: SettingsPage,
});

function SettingsPage() {
  const navigate = useNavigate();
  const [startingBalance, setStartingBalance] = useState("");
  const [monthlyExpenses, setMonthlyExpenses] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      navigate({ to: "/login" });
      return;
    }
    (async () => {
      try {
        const res = await apiFetch("/business/settings");
        if (res.status === 401) {
          navigate({ to: "/login" });
          return;
        }
        if (!res.ok) throw new Error("Failed to load settings");
        const data = await res.json();
        if (data?.starting_balance != null) {
          setStartingBalance(String(data.starting_balance));
        }
        if (data?.monthly_expenses != null) {
          setMonthlyExpenses(String(data.monthly_expenses));
        }
      } catch (e: unknown) {
        setErr(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    })();
  }, [navigate]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErr(null);
    try {
      const body = {
        starting_balance: Number(startingBalance) || 0,
        monthly_expenses: Number(monthlyExpenses) || 0,
      };
      const res = await apiFetch("/business/settings", {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Failed: ${res.status}`);
      }
      toast.success("Settings saved");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to save";
      toast.error(msg);
      setErr(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-white">
      <CrestNav />
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
        <h1 className="mb-6 text-2xl font-bold text-[#0f172a]">Business Settings</h1>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
          </div>
        ) : err && !saving ? (
          <p className="text-sm text-red-600">{err}</p>
        ) : (
          <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
            <div className="mb-5 flex items-center gap-2">
              <Settings className="h-5 w-5 text-[#0f172a]" />
              <h2 className="text-lg font-semibold text-[#0f172a]">Financial Settings</h2>
            </div>
            <form onSubmit={handleSave} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Current Bank Balance (₹)
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
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Monthly Operating Expenses (₹)
                </label>
                <input
                  type="number"
                  min="0"
                  value={monthlyExpenses}
                  onChange={(e) => setMonthlyExpenses(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-[#0f172a] focus:outline-none"
                />
              </div>
              <div className="sm:col-span-2">
                <button
                  type="submit"
                  disabled={saving}
                  className="inline-flex items-center gap-2 rounded-lg bg-[#0f172a] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#1e293b] disabled:opacity-60"
                >
                  {saving && (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  )}
                  Save
                </button>
              </div>
            </form>
          </section>
        )}
      </main>
    </div>
  );
}
