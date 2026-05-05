import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { fleetApi, type VehicleCreate, type VehicleOut } from "@/api/client";
import StatusBadge from "@/components/StatusBadge";
import ConfirmModal from "@/components/ConfirmModal";
import { Plus, Pencil, Trash2 } from "lucide-react";

type FormData = VehicleCreate & { id?: number };

const EMPTY: FormData = { plate: "", capacity: 1000, status: "available", notes: "" };

export default function FleetPage() {
  const [vehicles, setVehicles] = useState<VehicleOut[]>([]);
  const [form, setForm] = useState<FormData>(EMPTY);
  const [showForm, setShowForm] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  const load = () => fleetApi.list().then((r) => setVehicles(r.data)).catch(() => {});

  useEffect(() => { load(); }, []);

  const openCreate = () => { setForm(EMPTY); setShowForm(true); };
  const openEdit = (v: VehicleOut) => { setForm({ ...v }); setShowForm(true); };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (form.id) {
        const { id, ...rest } = form;
        await fleetApi.update(id!, rest);
        toast.success("Vehicle updated");
      } else {
        await fleetApi.create(form);
        toast.success("Vehicle added");
      }
      setShowForm(false);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail ?? "Error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await fleetApi.delete(deleteId);
      toast.success("Vehicle deleted");
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail ?? "Delete failed");
    } finally {
      setDeleteId(null);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Fleet</h1>
          <p className="text-sm text-gray-500">Manage transport vehicles</p>
        </div>
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
        >
          <Plus size={16} /> Add Vehicle
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 border-b">
              <th className="pb-2">Plate</th>
              <th className="pb-2">Capacity</th>
              <th className="pb-2">Status</th>
              <th className="pb-2">Notes</th>
              <th className="pb-2"></th>
            </tr>
          </thead>
          <tbody>
            {vehicles.map((v) => (
              <tr key={v.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="py-2 font-medium">{v.plate}</td>
                <td className="py-2">{v.capacity.toLocaleString()} kg</td>
                <td className="py-2"><StatusBadge status={v.status} /></td>
                <td className="py-2 text-gray-500 text-xs">{v.notes ?? "—"}</td>
                <td className="py-2 flex gap-1 justify-end">
                  <button onClick={() => openEdit(v)} className="p-1 text-gray-400 hover:text-blue-600"><Pencil size={15} /></button>
                  <button onClick={() => setDeleteId(v.id)} className="p-1 text-gray-400 hover:text-red-600"><Trash2 size={15} /></button>
                </td>
              </tr>
            ))}
            {vehicles.length === 0 && (
              <tr><td colSpan={5} className="py-8 text-center text-gray-400">No vehicles yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Form modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <form onSubmit={handleSave} className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4 space-y-4">
            <h3 className="font-semibold text-gray-900 text-lg">
              {form.id ? "Update Vehicle" : "Add New Vehicle"}
            </h3>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Plate *</label>
              <input value={form.plate} onChange={(e) => setForm({ ...form, plate: e.target.value })}
                required className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Capacity (kg) *</label>
              <input type="number" min={1} value={form.capacity} onChange={(e) => setForm({ ...form, capacity: Number(e.target.value) })}
                required className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as any })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
                <option value="available">Available</option>
                <option value="in_use">In Use</option>
                <option value="maintenance">Maintenance</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
              <textarea value={form.notes ?? ""} onChange={(e) => setForm({ ...form, notes: e.target.value })}
                rows={2} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none" />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={() => setShowForm(false)}
                className="px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50">
                Cancel
              </button>
              <button type="submit" disabled={saving}
                className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
                {saving ? "Saving..." : "Save"}
              </button>
            </div>
          </form>
        </div>
      )}

      <ConfirmModal
        open={deleteId !== null}
        title="Delete Vehicle"
        message={`Confirm delete vehicle #${deleteId}?`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
        danger
      />
    </div>
  );
}
