import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { CrestNav } from "@/components/CrestNav";
import { apiFetch, getToken } from "@/lib/crest";

export const Route = createFileRoute("/upload")({
  head: () => ({ meta: [{ title: "Upload Invoice — Crest" }] }),
  component: UploadPage,
});

function UploadPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) navigate({ to: "/login" });
  }, [navigate]);

  async function upload() {
    if (!file) return;
    setErr(null);
    setSuccess(null);
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await apiFetch("/invoices/upload/csv", { method: "POST", body: fd });
      const text = await res.text();
      let data: any = {};
      try { data = JSON.parse(text); } catch { data = { raw: text }; }
      console.log("Upload API Response:", { status: res.status, ok: res.ok, data });
      if (!res.ok) {
        throw new Error(data.detail || data.message || data.error || `Upload failed (${res.status}): ${text}`);
      }
      const count = data.imported ?? data.count ?? data.invoices_imported ?? data.imported_count ?? "";
      setSuccess(`Successfully imported ${count} invoices. ${data.message || ""}`);
      setFile(null);
      // Redirect to dashboard with a forced fresh fetch
      setTimeout(() => {
        window.location.href = "/dashboard";
      }, 800);
    } catch (e: any) {
      console.error("Upload error:", e);
      setErr(e.message || "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-white">
      <CrestNav />
      <main className="mx-auto max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
        <Link to="/dashboard" className="text-sm font-medium text-emerald-600 hover:underline">
          ← Back to Dashboard
        </Link>
        <h1 className="mt-4 text-2xl font-bold text-[#0f172a]">Upload Invoices</h1>
        <p className="mt-1 text-sm text-slate-500">Upload a CSV file of your invoices.</p>

        <div
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            const f = e.dataTransfer.files?.[0];
            if (f && f.name.endsWith(".csv")) setFile(f);
          }}
          onClick={() => inputRef.current?.click()}
          className={`mt-6 cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition ${
            drag ? "border-emerald-500 bg-emerald-50" : "border-slate-300 bg-white hover:bg-slate-50"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          <p className="text-sm text-slate-600">
            {file ? <span className="font-medium text-[#0f172a]">{file.name}</span> : "Click or drag a CSV file here"}
          </p>
          <p className="mt-1 text-xs text-slate-400">CSV files only</p>
        </div>

        {err && <p className="mt-4 text-sm text-red-600">{err}</p>}
        {success && (
          <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {success}
          </div>
        )}

        <button
          onClick={upload}
          disabled={!file || loading}
          className="mt-6 w-full rounded-lg bg-[#0f172a] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#1e293b] disabled:opacity-60 sm:w-auto sm:px-6"
        >
          {loading ? "Uploading..." : "Upload CSV"}
        </button>
      </main>
    </div>
  );
}
