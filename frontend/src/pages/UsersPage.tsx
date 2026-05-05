import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { usersApi, type UserCreate, type UserOut, type UserRole } from "@/api/client";
import StatusBadge from "@/components/StatusBadge";
import ConfirmModal from "@/components/ConfirmModal";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

const ROLE_BADGE: Record<UserRole, string> = {
  admin: "bg-red-100 text-red-700",
  algo_tester: "bg-blue-100 text-blue-700",
  dataset_provider: "bg-green-100 text-green-700",
  metric_provider: "bg-purple-100 text-purple-700",
};

interface FormData {
  id?: number;
  email: string;
  password: string;
  full_name: string;
  role: UserRole;
  is_active?: boolean;
}

const EMPTY: FormData = { email: "", password: "", full_name: "", role: "algo_tester" };

export default function UsersPage() {
  const { t } = useTranslation();
  const [users, setUsers] = useState<UserOut[]>([]);
  const [form, setForm] = useState<FormData>(EMPTY);
  const [showForm, setShowForm] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  const load = () => usersApi.list().then((r) => setUsers(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const openCreate = () => { setForm(EMPTY); setShowForm(true); };
  const openEdit = (u: UserOut) => { setForm({ ...u, password: "" }); setShowForm(true); };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (form.id) {
        const update: any = { full_name: form.full_name, role: form.role, is_active: form.is_active };
        if (form.password) update.password = form.password;
        await usersApi.update(form.id, update);
        toast.success(t("users.updateSuccess"));
      } else {
        await usersApi.create(form as UserCreate);
        toast.success(t("users.createSuccess"));
      }
      setShowForm(false);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail ?? t("users.errorDefault"));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await usersApi.delete(deleteId);
      toast.success(t("users.deleteSuccess"));
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail ?? t("users.deleteFailed"));
    } finally {
      setDeleteId(null);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t("users.title")}</h1>
          <p className="text-sm text-gray-500">{t("users.subtitle")}</p>
        </div>
        <button onClick={openCreate}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
          <Plus size={16} /> {t("users.createBtn")}
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 border-b">
              <th className="pb-2">{t("users.colName")}</th>
              <th className="pb-2">{t("users.colEmail")}</th>
              <th className="pb-2">{t("users.colRole")}</th>
              <th className="pb-2">{t("users.colStatus")}</th>
              <th className="pb-2">{t("users.colCreatedAt")}</th>
              <th className="pb-2"></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="py-2 font-medium">{u.full_name}</td>
                <td className="py-2 text-gray-500">{u.email}</td>
                <td className="py-2">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_BADGE[u.role] ?? "bg-gray-100 text-gray-700"}`}>
                    {t(`role.${u.role}`, { defaultValue: u.role })}
                  </span>
                </td>
                <td className="py-2">
                  <StatusBadge status={u.is_active ? "available" : "maintenance"} />
                </td>
                <td className="py-2 text-gray-500">{new Date(u.created_at).toLocaleDateString()}</td>
                <td className="py-2 flex gap-1 justify-end">
                  <button onClick={() => openEdit(u)} className="p-1 text-gray-400 hover:text-blue-600"><Pencil size={15} /></button>
                  <button onClick={() => setDeleteId(u.id)} className="p-1 text-gray-400 hover:text-red-600"><Trash2 size={15} /></button>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr><td colSpan={6} className="py-8 text-center text-gray-400">{t("users.noUsers")}</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <form onSubmit={handleSave} className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4 space-y-4">
            <h3 className="font-semibold text-gray-900 text-lg">
              {form.id ? t("users.formEditTitle") : t("users.formCreateTitle")}
            </h3>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t("users.fieldName")}</label>
              <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                required className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
            </div>
            {!form.id && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t("users.fieldEmail")}</label>
                <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                  required className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {form.id ? t("users.fieldPasswordEdit") : t("users.fieldPassword")}
              </label>
              <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
                required={!form.id} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t("users.fieldRole")}</label>
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
                <option value="admin">{t("role.admin")}</option>
                <option value="algo_tester">{t("role.algo_tester")}</option>
                <option value="dataset_provider">{t("role.dataset_provider")}</option>
                <option value="metric_provider">{t("role.metric_provider")}</option>
              </select>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={() => setShowForm(false)}
                className="px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50">{t("btn.cancel")}</button>
              <button type="submit" disabled={saving}
                className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
                {saving ? t("btn.saving") : t("btn.save")}
              </button>
            </div>
          </form>
        </div>
      )}

      <ConfirmModal
        open={deleteId !== null}
        title={t("users.deleteTitle")}
        message={t("users.deleteMsg", { id: deleteId })}
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
        danger
      />
    </div>
  );
}
