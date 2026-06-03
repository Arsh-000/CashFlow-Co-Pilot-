import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { CrestLogo } from "@/components/CrestLogo";
import { API_BASE, setToken } from "@/lib/crest";

export const Route = createFileRoute("/signup")({
  head: () => ({ meta: [{ title: "Sign up — Crest" }] }),
  component: SignupPage,
});

function SignupPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    business_name: "",
    city: "",
    phone: "",
    email: "",
    password: "",
  });
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function up<K extends keyof typeof form>(k: K, v: string) {
    setForm({ ...form, [k]: v });
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);

    if (!form.business_name || !form.city || !form.phone || !form.email || !form.password) {
      setErr("All fields are required");
      return;
    }
    if (!/^\d{10}$/.test(form.phone)) {
      setErr("Phone must be exactly 10 digits");
      return;
    }
    if (form.password.length < 8) {
      setErr("Password must be at least 8 characters");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json().catch(() => ({} as any));
      if (!res.ok) {
        throw new Error(data.detail || data.message || "Signup failed");
      }
      if (data.access_token) setToken(data.access_token);
      navigate({ to: "/dashboard" });
    } catch (e: any) {
      setErr(e.message || "Signup failed");
    } finally {
      setLoading(false);
    }
  }

  const fields: {
    k: keyof typeof form;
    label: string;
    type?: string;
    placeholder: string;
    inputMode?: "numeric";
    maxLength?: number;
  }[] = [
    { k: "business_name", label: "Business Name", placeholder: "Arsh Traders" },
    { k: "city", label: "City", placeholder: "Coimbatore / Tiruppur / Chennai" },
    { k: "phone", label: "Phone", type: "tel", placeholder: "9876543210", inputMode: "numeric", maxLength: 10 },
    { k: "email", label: "Email", type: "email", placeholder: "you@example.com" },
    { k: "password", label: "Password", type: "password", placeholder: "Min 8 characters" },
  ];

  return (
    <div className="flex min-h-screen items-center justify-center bg-white px-4 py-8">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <CrestLogo />
          <p className="mt-2 text-sm text-slate-500">Your business at its peak</p>
        </div>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          {fields.map((f) => (
            <div key={f.k}>
              <label className="mb-1 block text-sm font-medium text-slate-700">{f.label}</label>
              <input
                type={f.type || "text"}
                value={form[f.k]}
                onChange={(e) => {
                  const v = f.k === "phone" ? e.target.value.replace(/\D/g, "").slice(0, 10) : e.target.value;
                  up(f.k, v);
                }}
                placeholder={f.placeholder}
                inputMode={f.inputMode}
                maxLength={f.maxLength}
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-[#0f172a]"
              />
            </div>
          ))}
          {err && <p className="text-sm text-red-600">{err}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-[#0f172a] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#1e293b] disabled:opacity-60"
          >
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-slate-600">
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-emerald-600 hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
