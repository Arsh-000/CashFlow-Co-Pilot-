import { Link, useNavigate } from "@tanstack/react-router";
import { CrestLogo } from "./CrestLogo";
import { InstallAppButton } from "./InstallAppButton";
import { clearToken } from "@/lib/crest";

export function CrestNav() {
  const navigate = useNavigate();
  const logout = () => {
    clearToken();
    navigate({ to: "/login" });
  };
  return (
    <nav className="w-full border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
        <Link to="/dashboard"><CrestLogo /></Link>
        <div className="hidden gap-6 sm:flex">
          <Link
            to="/dashboard"
            className="text-sm font-medium text-slate-700 hover:text-[#0f172a]"
            activeProps={{ className: "text-sm font-semibold text-[#0f172a]" }}
          >
            Dashboard
          </Link>
          <Link
            to="/upload"
            className="text-sm font-medium text-slate-700 hover:text-[#0f172a]"
            activeProps={{ className: "text-sm font-semibold text-[#0f172a]" }}
          >
            Upload Invoice
          </Link>
          <Link
            to="/insights"
            className="text-sm font-medium text-slate-700 hover:text-[#0f172a]"
            activeProps={{ className: "text-sm font-semibold text-[#0f172a]" }}
          >
            AI Insights
          </Link>
          <Link
            to="/settings"
            className="text-sm font-medium text-slate-700 hover:text-[#0f172a]"
            activeProps={{ className: "text-sm font-semibold text-[#0f172a]" }}
          >
            Settings
          </Link>
        </div>
        <div className="flex items-center gap-2">
          <InstallAppButton />
          <button
            onClick={logout}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
          >
            Logout
          </button>
        </div>
      </div>
      <div className="mx-auto flex max-w-7xl gap-4 px-4 pb-3 sm:hidden">
        <Link to="/dashboard" className="text-sm font-medium text-slate-700">Dashboard</Link>
        <Link to="/upload" className="text-sm font-medium text-slate-700">Upload Invoice</Link>
        <Link to="/insights" className="text-sm font-medium text-slate-700">AI Insights</Link>
        <Link to="/settings" className="text-sm font-medium text-slate-700">Settings</Link>
      </div>
    </nav>
  );
}
