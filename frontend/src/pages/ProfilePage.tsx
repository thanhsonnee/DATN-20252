import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";
import api from "@/api/client";
import { useAuth } from "@/contexts/AuthContext";
import { useTranslation } from "react-i18next";

interface UserInfo {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  registered_at: string;
}

export default function ProfilePage() {
  const { t } = useTranslation();
  const { user, login, token } = useAuth();
  const [info, setInfo] = useState<UserInfo | null>(null);

  // Edit full_name
  const [editName, setEditName] = useState("");
  const [savingName, setSavingName] = useState(false);


  // ── Load user info from API ──
  useEffect(() => {
    if (!user) return;
    api
      .get(`/users/${user.user_id}`)
      .then((r) => {
        const d: UserInfo = r.data.data;
        setInfo(d);
        setEditName(d.full_name);
      })
      .catch(() => toast.error(t("profile.loadError")));
  }, [user]);

  // ── set_user_info (full_name) ──
  const handleSaveName = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!info) return;
    setSavingName(true);
    try {
      const r = await api.patch(`/users/me`, { full_name: editName });
      const updated: UserInfo = r.data.data;
      setInfo(updated);
      // sync context so sidebar name updates
      if (user && token) {
        login(token, { ...user, full_name: updated.full_name });
      }
      toast.success(t("profile.updateSuccess"));
    } catch (e: any) {
      toast.error(e.response?.data?.detail ?? t("profile.updateFailed"));
    } finally {
      setSavingName(false);
    }
  };


  if (!info) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
        {t("profile.loading")}
      </div>
    );
  }

  return (
    <div className="max-w-md space-y-5">
      <h1 className="text-2xl font-bold text-gray-900">{t("profile.title")}</h1>

      {/* ── Info ── */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="flex items-center gap-4 mb-5">
          <div className="w-14 h-14 rounded-full bg-blue-500 flex items-center justify-center text-xl font-bold text-white uppercase flex-shrink-0">
            {info.full_name?.[0] ?? "?"}
          </div>
          <div>
            <p className="font-semibold text-gray-900">{info.full_name}</p>
            <p className="text-sm text-gray-500">{info.email}</p>
            <span className="mt-1 inline-block px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-700 font-medium">
              {t(`role.${info.role}`, { defaultValue: info.role })}
            </span>
          </div>
        </div>

        <div className="text-xs text-gray-400 space-y-1">
          <p>{t("profile.idLabel")} #{info.id}</p>
          <p>{t("profile.registeredAt")} {new Date(info.registered_at).toLocaleString()}</p>
          <p>
            {t("profile.statusLabel")}{" "}
            <span className={info.is_active ? "text-green-600 font-medium" : "text-red-500 font-medium"}>
              {info.is_active ? t("status.active") : t("status.disabled")}
            </span>
          </p>
        </div>
      </div>

      {/* ── Edit name ── */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("profile.updateNameTitle")}</h2>
        <form onSubmit={handleSaveName} className="space-y-3">
          <input
            type="text"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            required
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder={t("profile.namePlaceholder")}
          />
          <button
            type="submit"
            disabled={savingName || editName === info.full_name}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-medium py-2 rounded-lg text-sm"
          >
            {savingName ? t("btn.saving") : t("btn.save")}
          </button>
        </form>
      </div>

    </div>
  );
}
