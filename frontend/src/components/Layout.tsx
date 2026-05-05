import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import ConfirmModal from "@/components/ConfirmModal";
import { useTranslation } from "react-i18next";
import i18n from "@/i18n";
import {
  LayoutDashboard,
  FileText,
  PlayCircle,
  Users,
  LogOut,
  Menu,
  X,
  FlaskConical,
  BarChart2,
  Ruler,
} from "lucide-react";

interface NavItem {
  labelKey: string;
  to: string;
  icon: React.ReactNode;
  roles: string[];
}

const NAV: NavItem[] = [
  { labelKey: "nav.dashboard",   to: "/",           icon: <LayoutDashboard size={18} />, roles: ["admin", "algo_tester", "dataset_provider", "metric_provider"] },
  { labelKey: "nav.instances",   to: "/instances",  icon: <FileText size={18} />,        roles: ["admin", "algo_tester", "dataset_provider"] },
  { labelKey: "nav.algorithms",  to: "/algorithms", icon: <FlaskConical size={18} />,    roles: ["admin", "algo_tester"] },
  { labelKey: "nav.metrics",     to: "/metrics",    icon: <Ruler size={18} />,            roles: ["admin", "metric_provider"] },
  { labelKey: "nav.jobs",        to: "/jobs",       icon: <PlayCircle size={18} />,      roles: ["admin", "algo_tester"] },
  { labelKey: "nav.comparison",  to: "/comparison", icon: <BarChart2 size={18} />,       roles: ["admin", "algo_tester"] },
  { labelKey: "nav.users",       to: "/users",      icon: <Users size={18} />,           roles: ["admin"] },
];

function LanguageToggle({ collapsed }: { collapsed: boolean }) {
  const { i18n: i18nInstance } = useTranslation();
  const currentLang = i18nInstance.language === "en" ? "en" : "vi";

  const toggle = () => {
    const next = currentLang === "vi" ? "en" : "vi";
    i18nInstance.changeLanguage(next);
    localStorage.setItem("lang", next);
  };

  if (collapsed) {
    return (
      <button
        onClick={toggle}
        className="text-xs font-bold text-gray-400 hover:text-white transition-colors"
        title="Switch language"
      >
        {currentLang.toUpperCase()}
      </button>
    );
  }

  return (
    <div className="flex items-center gap-1 text-xs">
      <button
        onClick={() => { i18nInstance.changeLanguage("vi"); localStorage.setItem("lang", "vi"); }}
        className={`px-1.5 py-0.5 rounded font-semibold transition-colors ${
          currentLang === "vi"
            ? "bg-blue-600 text-white"
            : "text-gray-400 hover:text-white"
        }`}
      >
        VI
      </button>
      <span className="text-gray-600">|</span>
      <button
        onClick={() => { i18nInstance.changeLanguage("en"); localStorage.setItem("lang", "en"); }}
        className={`px-1.5 py-0.5 rounded font-semibold transition-colors ${
          currentLang === "en"
            ? "bg-blue-600 text-white"
            : "text-gray-400 hover:text-white"
        }`}
      >
        EN
      </button>
    </div>
  );
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(true);
  const [confirmLogout, setConfirmLogout] = useState(false);

  const visibleNav = NAV.filter((n) => user && n.roles.includes(user.role));

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      <ConfirmModal
        open={confirmLogout}
        title={t("layout.logout")}
        message={t("layout.logoutConfirm")}
        onConfirm={handleLogout}
        onCancel={() => setConfirmLogout(false)}
        danger
      />
      {/* Sidebar */}
      <aside
        className={`flex flex-col bg-gray-900 text-gray-100 transition-all duration-200 ${
          open ? "w-56" : "w-14"
        } flex-shrink-0`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-4 border-b border-gray-700">
          {open && (
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  {/* Route 1: top-left → bottom-right (S-curve) */}
                  <path d="M4 4 C 4 12 20 12 20 20" stroke="white" strokeWidth="1.8" strokeLinecap="round" opacity="0.9"/>
                  {/* Route 2: top-right → bottom-left (S-curve) */}
                  <path d="M20 4 C 20 12 4 12 4 20" stroke="white" strokeWidth="1.8" strokeLinecap="round" opacity="0.9"/>
                  {/* 4 endpoint nodes (pickup / delivery points) */}
                  <circle cx="4" cy="4" r="2" fill="white"/>
                  <circle cx="20" cy="4" r="2" fill="white"/>
                  <circle cx="4" cy="20" r="2" fill="white"/>
                  <circle cx="20" cy="20" r="2" fill="white"/>
                  {/* Center hub (depot) */}
                  <circle cx="12" cy="12" r="2.8" fill="white"/>
                </svg>
              </div>
              <span className="text-sm font-bold text-white truncate">RouteX</span>
            </div>
          )}
          <button
            onClick={() => setOpen(!open)}
            className="text-gray-400 hover:text-white ml-auto"
          >
            {open ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>

        {/* Nav items */}
        <nav className="flex-1 overflow-y-auto py-3 space-y-1 px-2">
          {visibleNav.map((item) => {
            const active = pathname === item.to || (item.to !== "/" && pathname.startsWith(item.to));
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`flex items-center gap-3 px-2 py-2 rounded-lg text-sm transition-colors ${
                  active
                    ? "bg-blue-600 text-white"
                    : "text-gray-400 hover:bg-gray-800 hover:text-white"
                }`}
              >
                <span className="flex-shrink-0">{item.icon}</span>
                {open && <span className="truncate">{t(item.labelKey)}</span>}
              </Link>
            );
          })}
        </nav>

        {/* User footer */}
        <div className="border-t border-gray-700 p-3">
          {open ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Link to="/profile" className="flex items-center gap-2 flex-1 min-w-0 hover:opacity-80">
                  <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-xs font-bold uppercase flex-shrink-0">
                    {user?.full_name?.[0] ?? "?"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium truncate">{user?.full_name}</p>
                    <p className="text-xs text-gray-400 truncate capitalize">{user?.role}</p>
                  </div>
                </Link>
                <button onClick={() => setConfirmLogout(true)} className="text-gray-400 hover:text-red-400">
                  <LogOut size={16} />
                </button>
              </div>
              <div className="flex items-center justify-end">
                <LanguageToggle collapsed={false} />
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <Link to="/profile" className="hover:opacity-80">
                <div className="w-7 h-7 rounded-full bg-blue-500 flex items-center justify-center text-xs font-bold uppercase">
                  {user?.full_name?.[0] ?? "?"}
                </div>
              </Link>
              <button onClick={() => setConfirmLogout(true)} className="text-gray-400 hover:text-red-400">
                <LogOut size={16} />
              </button>
              <LanguageToggle collapsed={true} />
            </div>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-6">{children}</main>
    </div>
  );
}
