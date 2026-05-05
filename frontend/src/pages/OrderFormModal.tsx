import React, { useState } from "react";
import toast from "react-hot-toast";
import { ordersApi, type OrderCreate, type OrderOut } from "@/api/client";

interface Props {
  order?: OrderOut;
  onClose: () => void;
  onSaved: () => void;
}

export default function OrderFormModal({ order, onClose, onSaved }: Props) {
  const [form, setForm] = useState<OrderCreate>({
    pickup_address: order?.pickup_address ?? "",
    delivery_address: order?.delivery_address ?? "",
    description: order?.description ?? "",
    time_window_start: order?.time_window_start ?? "",
    time_window_end: order?.time_window_end ?? "",
  });
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (order) {
        await ordersApi.update(order.id, form);
        toast.success("Order updated");
      } else {
        await ordersApi.create(form);
        toast.success("Order created");
      }
      onSaved();
    } catch (e: any) {
      toast.error(e.response?.data?.detail ?? "Error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4 space-y-4">
        <h3 className="font-semibold text-gray-900 text-lg">
          {order ? "Update order" : "Create new order"}
        </h3>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Pickup address *</label>
          <input value={form.pickup_address} onChange={(e) => setForm({ ...form, pickup_address: e.target.value })}
            required className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" placeholder="Street, district, city" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Delivery address *</label>
          <input value={form.delivery_address} onChange={(e) => setForm({ ...form, delivery_address: e.target.value })}
            required className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" placeholder="Street, district, city" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Earliest pickup time</label>
            <input type="time" value={form.time_window_start ?? ""} onChange={(e) => setForm({ ...form, time_window_start: e.target.value })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Latest pickup time</label>
            <input type="time" value={form.time_window_end ?? ""} onChange={(e) => setForm({ ...form, time_window_end: e.target.value })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
          <textarea value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={2} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none" placeholder="Describe the cargo, special requirements..." />
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50">Cancel</button>
          <button type="submit" disabled={saving} className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </form>
    </div>
  );
}
