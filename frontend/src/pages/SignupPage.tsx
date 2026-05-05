import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { authApi } from "@/api/client";

type Role = "algo_tester" | "dataset_provider" | "metric_provider";

const ROLE_LABELS: Record<Role, string> = {
  algo_tester: "Algo Tester",
  dataset_provider: "Dataset Provider",
  metric_provider: "Metric Provider",
};

export default function SignupPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "", confirm: "", full_name: "", role: "algo_tester" as Role });
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.password !== form.confirm) {
      toast.error("Passwords do not match");
      return;
    }
    setLoading(true);
    try {
      await authApi.signup(form.email, form.password, form.full_name, form.role);
      setDone(true);
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-blue-100">
        <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-sm text-center">
          <div className="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Registration successful!</h2>
          <p className="text-sm text-gray-500 mb-6">
            Please check your email <strong>{form.email}</strong> and click the verification link to activate your account.
          </p>
          <button
            onClick={() => navigate("/login")}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 rounded-lg text-sm"
          >
            Back to login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-blue-100">
      <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center flex-shrink-0">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path d="M4 4 C 4 12 20 12 20 20" stroke="white" strokeWidth="1.8" strokeLinecap="round" opacity="0.9"/>
              <path d="M20 4 C 20 12 4 12 4 20" stroke="white" strokeWidth="1.8" strokeLinecap="round" opacity="0.9"/>
              <circle cx="4" cy="4" r="2" fill="white"/>
              <circle cx="20" cy="4" r="2" fill="white"/>
              <circle cx="4" cy="20" r="2" fill="white"/>
              <circle cx="20" cy="20" r="2" fill="white"/>
              <circle cx="12" cy="12" r="2.8" fill="white"/>
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">RouteX</h1>
        </div>
        <p className="text-sm text-gray-500 mb-6">Create a new account</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Full name</label>
            <input
              type="text"
              value={form.full_name}
              onChange={set("full_name")}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="John Doe"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email <span className="text-red-500">*</span></label>
            <input
              type="email"
              value={form.email}
              onChange={set("email")}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="email@example.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
            <select
              value={form.role}
              onChange={set("role")}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
                <option key={r} value={r}>{ROLE_LABELS[r]}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password <span className="text-red-500">*</span></label>
            <input
              type="password"
              value={form.password}
              onChange={set("password")}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter password"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Confirm password <span className="text-red-500">*</span></label>
            <input
              type="password"
              value={form.confirm}
              onChange={set("confirm")}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Re-enter password"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium py-2 rounded-lg text-sm transition-colors"
          >
            {loading ? "Registering..." : "Register"}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500 mt-4">
          Already have an account?{" "}
          <Link to="/login" className="text-blue-600 hover:underline font-medium">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
