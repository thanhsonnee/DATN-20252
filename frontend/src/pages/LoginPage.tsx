import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { authApi } from "@/api/client";
import { useAuth } from "@/contexts/AuthContext";
import { useTranslation } from "react-i18next";

export default function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await authApi.login(email, password);
      login(data.access_token, {
        user_id: data.user_id,
        email,
        full_name: data.full_name,
        role: data.role,
      });
      navigate("/");
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? t("login.errorDefault"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-blue-100">
      <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center flex-shrink-0">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M4 4 C 4 12 20 12 20 20" stroke="white" strokeWidth="1.8" strokeLinecap="round" opacity="0.9"/>
              <path d="M20 4 C 20 12 4 12 4 20" stroke="white" strokeWidth="1.8" strokeLinecap="round" opacity="0.9"/>
              <circle cx="4" cy="4" r="2" fill="white"/>
              <circle cx="20" cy="4" r="2" fill="white"/>
              <circle cx="4" cy="20" r="2" fill="white"/>
              <circle cx="20" cy="20" r="2" fill="white"/>
              <circle cx="12" cy="12" r="2.8" fill="white"/>
            </svg>
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 leading-none">RouteX</h1>
          </div>
        </div>
        <p className="text-sm text-gray-500 mb-6">{t("login.subtitle")}</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("login.email")}</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="email@example.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("login.password")}</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="••••••••"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium py-2 rounded-lg text-sm transition-colors"
          >
            {loading ? t("login.submitting") : t("login.submit")}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500 mt-4">
          {t("login.noAccount")}{" "}
          <Link to="/signup" className="text-blue-600 hover:underline font-medium">
            {t("login.register")}
          </Link>
        </p>
      </div>
    </div>
  );
}
