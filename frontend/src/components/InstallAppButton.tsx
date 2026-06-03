import { useEffect, useState } from "react";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

export function InstallAppButton() {
  const [evt, setEvt] = useState<BeforeInstallPromptEvent | null>(null);

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setEvt(e as BeforeInstallPromptEvent);
    };
    const installed = () => setEvt(null);
    window.addEventListener("beforeinstallprompt", handler);
    window.addEventListener("appinstalled", installed);
    return () => {
      window.removeEventListener("beforeinstallprompt", handler);
      window.removeEventListener("appinstalled", installed);
    };
  }, []);

  if (!evt) return null;

  return (
    <button
      onClick={async () => {
        const e = evt;
        setEvt(null);
        try {
          await e.prompt();
          await e.userChoice;
        } catch {
          /* noop */
        }
      }}
      className="rounded-lg bg-[#0f172a] px-3 py-1.5 text-sm font-medium text-white transition hover:bg-[#1e293b]"
    >
      Install App
    </button>
  );
}
