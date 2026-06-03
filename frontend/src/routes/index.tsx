import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { BarChart3, TrendingUp, MessageCircle } from "lucide-react";

const SCREENS = [
  {
    icon: BarChart3,
    iconColor: "text-emerald-600",
    iconBg: "bg-emerald-50",
    headline: "Know Who Owes You",
    subtext: "See all your outstanding invoices and overdue customers in one place",
    tamil: "யார் கடன் பட்டிருக்கிறார்கள் என்று உடனே தெரியும்",
  },
  {
    icon: TrendingUp,
    iconColor: "text-sky-600",
    iconBg: "bg-sky-50",
    headline: "See Your Cash 30 Days Ahead",
    subtext: "AI predicts your cash position so you're never caught off guard",
    tamil: "30 நாட்களில் உங்கள் பணம் எவ்வளவு இருக்கும் என்று தெரியும்",
  },
  {
    icon: MessageCircle,
    iconColor: "text-green-600",
    iconBg: "bg-green-50",
    headline: "Auto-Remind Late Payers",
    subtext: "WhatsApp reminders sent automatically to customers with overdue invoices",
    tamil: "தாமதமான வாடிக்கையாளர்களுக்கு தானாக WhatsApp அனுப்பும்",
  },
];

export const Route = createFileRoute("/")({
  head: () => ({ meta: [{ title: "Welcome — Crest" }] }),
  component: OnboardingPage,
});

function OnboardingPage() {
  const navigate = useNavigate();
  const [screen, setScreen] = useState(0);
  const [direction, setDirection] = useState<"left" | "right">("right");
  const [isTransitioning, setIsTransitioning] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const done = localStorage.getItem("crest_onboarding_done");
    if (done === "true") {
      navigate({ to: "/login" });
    }
  }, [navigate]);

  function goTo(next: number) {
    if (isTransitioning) return;
    setDirection(next > screen ? "right" : "left");
    setIsTransitioning(true);
    setTimeout(() => {
      setScreen(next);
      setIsTransitioning(false);
    }, 200);
  }

  function finish() {
    if (typeof window !== "undefined") {
      localStorage.setItem("crest_onboarding_done", "true");
    }
    navigate({ to: "/login" });
  }

  const current = SCREENS[screen];
  const Icon = current.icon;
  const isLast = screen === SCREENS.length - 1;

  const slideClass =
    direction === "right"
      ? isTransitioning
        ? "opacity-0 translate-x-8"
        : "opacity-100 translate-x-0"
      : isTransitioning
        ? "opacity-0 -translate-x-8"
        : "opacity-100 translate-x-0";

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-white px-6">
      <div className="w-full max-w-sm">
        {/* Screen content */}
        <div className={`flex flex-col items-center text-center transition-all duration-200 ease-out ${slideClass}`}>
          {/* Icon */}
          <div
            className={`mb-8 flex h-20 w-20 items-center justify-center rounded-3xl ${current.iconBg}`}
          >
            <Icon className={`h-10 w-10 ${current.iconColor}`} strokeWidth={1.8} />
          </div>

          {/* Headline */}
          <h1 className="text-2xl font-bold tracking-tight text-[#0f172a]">
            {current.headline}
          </h1>

          {/* Subtext */}
          <p className="mt-3 text-[15px] leading-relaxed text-slate-500">
            {current.subtext}
          </p>

          {/* Tamil line */}
          <p className="mt-4 text-sm leading-relaxed text-slate-400">
            {current.tamil}
          </p>
        </div>

        {/* Dots */}
        <div className="mt-10 flex items-center justify-center gap-2">
          {SCREENS.map((_, i) => (
            <button
              key={i}
              onClick={() => goTo(i)}
              className={`h-2 rounded-full transition-all duration-300 ${
                i === screen
                  ? "w-6 bg-[#0f172a]"
                  : "w-2 bg-slate-200 hover:bg-slate-300"
              }`}
              aria-label={`Go to screen ${i + 1}`}
            />
          ))}
        </div>

        {/* Actions */}
        <div className="mt-8 flex flex-col gap-3">
          <button
            onClick={() => {
              if (isLast) {
                finish();
              } else {
                goTo(screen + 1);
              }
            }}
            className="w-full rounded-xl bg-[#0f172a] px-4 py-3.5 text-sm font-semibold text-white transition hover:bg-[#1e293b] active:scale-[0.98]"
          >
            {isLast ? "Get Started" : "Next"}
          </button>

          {!isLast && (
            <button
              onClick={finish}
              className="w-full py-2 text-sm font-medium text-slate-400 transition hover:text-slate-600"
            >
              Skip
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
