import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { CrestNav } from "@/components/CrestNav";
import { apiFetch, formatINR, getToken } from "@/lib/crest";

export const Route = createFileRoute("/insights")({
  head: () => ({ meta: [{ title: "AI Insights — Crest" }] }),
  component: InsightsPage,
});

type ChatMsg = { role: "user" | "ai"; content: string };

type TopRisk = {
  name?: string;
  total_outstanding?: number;
  max_days_overdue?: number;
};

type InsightData = {
  summary?: string;
  top_risks?: TopRisk[];
  urgent_action?: string;
  tamil_summary?: string;
};

const SUGGESTIONS = [
  "Which customer owes the most?",
  "What is my cash position next month?",
  "Who are my highest risk customers?",
];

function cleanMarkdown(text?: string) {
  if (!text) return "";
  return text.replace(/##?\s?/g, "").trim();
}

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function TypingDots() {
  return (
    <div className="flex gap-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-2 w-2 animate-bounce rounded-full bg-slate-400"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}

function InsightsPage() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [focused, setFocused] = useState(false);
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const [insight, setInsight] = useState<InsightData | null>(null);
  const [genLoading, setGenLoading] = useState(false);
  const [genErr, setGenErr] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      navigate({ to: "/login" });
      return;
    }
    (async () => {
      try {
        const res = await apiFetch("/insights/latest");
        if (res.ok) {
          const data = await res.json();
          if (data) setInsight(data);
        }
      } catch {
        /* ignore */
      }
    })();
  }, [navigate]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  async function sendMessage(question: string) {
    const q = question.trim();
    if (!q || sending) return;
    setMessages((m) => [...m, { role: "user", content: q }]);
    setInput("");
    setSending(true);
    try {
      const res = await apiFetch("/insights/chat", {
        method: "POST",
        body: JSON.stringify({ question: q }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(`${res.status} - ${t}`);
      }
      const data = await res.json();
      setMessages((m) => [...m, { role: "ai", content: data.answer || "(no answer)" }]);
    } catch (e: unknown) {
      setMessages((m) => [
        ...m,
        { role: "ai", content: `Error: ${getErrorMessage(e, "Failed")}` },
      ]);
    } finally {
      setSending(false);
    }
  }

  async function generateInsights() {
    setGenLoading(true);
    setGenErr(null);
    try {
      const res = await apiFetch("/insights/generate", { method: "POST" });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(`Failed: ${res.status} - ${t}`);
      }
      const data = await res.json();
      setInsight(data);
    } catch (e: unknown) {
      setGenErr(getErrorMessage(e, "Failed"));
    } finally {
      setGenLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-white">
      <CrestNav />
      <main className="mx-auto max-w-4xl px-4 py-6 sm:px-6 sm:py-8">
        <h1 className="mb-6 text-2xl font-bold text-[#0f172a]">AI Insights</h1>

        {/* CHAT SECTION */}
        <section className="rounded-2xl border border-slate-200 bg-white">
          <h2 className="border-b border-slate-200 px-5 py-4 text-lg font-semibold text-[#0f172a]">
            Ask Crest AI
          </h2>
          <div
            ref={scrollRef}
            className="flex h-96 flex-col gap-3 overflow-y-auto px-5 py-4"
          >
            {messages.length === 0 && !sending && (
              <div className="flex h-full items-center justify-center text-center text-sm text-slate-500">
                Ask me anything about your business finances 💬
              </div>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[75%] whitespace-pre-line rounded-2xl px-4 py-2 text-sm ${
                    m.role === "user"
                      ? "bg-[#0f172a] text-white"
                      : "bg-slate-100 text-slate-800"
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="rounded-2xl bg-slate-100 px-4 py-3">
                  <TypingDots />
                </div>
              </div>
            )}
          </div>

          <div className="border-t border-slate-200 px-5 py-3">
            {focused && input.length === 0 && (
              <div className="mb-3 flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      sendMessage(s);
                    }}
                    className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-100"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                sendMessage(input);
              }}
              className="flex gap-2"
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onFocus={() => setFocused(true)}
                onBlur={() => setTimeout(() => setFocused(false), 150)}
                placeholder="Type your question..."
                className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-[#0f172a]"
              />
              <button
                type="submit"
                disabled={sending || !input.trim()}
                className="rounded-lg bg-[#0f172a] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#1e293b] disabled:opacity-60"
              >
                Send
              </button>
            </form>
          </div>
        </section>

        {/* GENERATED INSIGHTS */}
        <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-[#0f172a]">
              <span aria-hidden>✨</span> Latest AI Insights
            </h2>
            <button
              onClick={generateInsights}
              disabled={genLoading}
              className="rounded-lg bg-[#0f172a] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#1e293b] disabled:opacity-60"
            >
              {genLoading ? "Generating..." : "Generate Insights"}
            </button>
          </div>

          {genErr && <p className="text-sm text-red-600">{genErr}</p>}
          {genLoading && (
            <div className="space-y-3">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="h-16 animate-pulse rounded-lg bg-slate-100" />
              ))}
            </div>
          )}

          {insight && !genLoading && (
            <div className="space-y-4">
              {insight.summary && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <h3 className="mb-1 text-sm font-semibold text-slate-800">Summary</h3>
                  <p className="whitespace-pre-line text-sm text-slate-800">
                    {cleanMarkdown(insight.summary)}
                  </p>
                </div>
              )}

              {insight.top_risks && insight.top_risks.length > 0 && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <h3 className="mb-2 text-sm font-semibold text-slate-800">
                    Top 3 Risky Customers
                  </h3>
                  <ol className="space-y-2 pl-5 text-sm text-slate-800">
                    {insight.top_risks.map((r, i) => (
                      <li key={i} className="list-decimal">
                        <span className="font-medium">{r.name || "—"}</span>
                        {" — "}
                        {formatINR(r.total_outstanding)}
                        {" • "}
                        {r.max_days_overdue ?? 0} days overdue
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {insight.urgent_action && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                  <h3 className="mb-1 text-sm font-semibold text-amber-900">Urgent Action</h3>
                  <p className="whitespace-pre-line text-sm text-amber-900">
                    {cleanMarkdown(insight.urgent_action)}
                  </p>
                </div>
              )}

              {insight.tamil_summary && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <h3 className="mb-1 flex items-center gap-2 text-sm font-semibold text-slate-800">
                    <span aria-hidden>🇮🇳</span> Tamil Summary
                  </h3>
                  <p className="whitespace-pre-line text-sm text-slate-800">
                    {insight.tamil_summary}
                  </p>
                </div>
              )}
            </div>
          )}

          {!insight && !genLoading && !genErr && (
            <p className="text-sm text-slate-500">
              No insights yet. Click "Generate Insights" to create one.
            </p>
          )}
        </section>
      </main>
    </div>
  );
}
