import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { ordersApi, type OrderCreate, type OrderOut } from "@/api/client";
import { useAuth } from "@/contexts/AuthContext";
import StatusBadge from "@/components/StatusBadge";
import ConfirmModal from "@/components/ConfirmModal";
import { Plus, Pencil, Trash2, Eye } from "lucide-react";
import OrderFormModal from "./OrderFormModal";
import OrderDetailModal from "./OrderDetailModal";

export default function OrdersPage() {
  const { isResearcher } = useAuth();
  const [orders, setOrders] = useState<OrderOut[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [editOrder, setEditOrder] = useState<OrderOut | null>(null);
  const [viewOrder, setViewOrder] = useState<OrderOut | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const load = () => ordersApi.list().then((r) => setOrders(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await ordersApi.delete(deleteId);
      toast.success("Order deleted");
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
          <h1 className="text-2xl font-bold text-gray-900">Orders</h1>
          <p className="text-sm text-gray-500">Track and manage delivery orders</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
        >
          <Plus size={16} /> Create order
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 border-b">
              <th className="pb-2">ID</th>
              <th className="pb-2">Pickup</th>
              <th className="pb-2">Delivery</th>
              <th className="pb-2">Time window</th>
              <th className="pb-2">Status</th>
              <th className="pb-2">Created</th>
              <th className="pb-2"></th>
            </tr>
          </thead>
          <tbody>
            {orders.map((o) => (
              <tr key={o.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="py-2 text-gray-500">#{o.id}</td>
                <td className="py-2 max-w-xs truncate">{o.pickup_address}</td>
                <td className="py-2 max-w-xs truncate">{o.delivery_address}</td>
                <td className="py-2 text-xs text-gray-500">
                  {o.time_window_start && o.time_window_end
                    ? `${o.time_window_start} – ${o.time_window_end}`
                    : "—"}
                </td>
                <td className="py-2"><StatusBadge status={o.status} /></td>
                <td className="py-2 text-gray-500">{new Date(o.created_at).toLocaleDateString()}</td>
                <td className="py-2 flex gap-1 justify-end">
                  <button onClick={() => setViewOrder(o)} className="p-1 text-gray-400 hover:text-blue-600"><Eye size={15} /></button>
                  <button onClick={() => setEditOrder(o)} className="p-1 text-gray-400 hover:text-blue-600"><Pencil size={15} /></button>
                  <button onClick={() => setDeleteId(o.id)} className="p-1 text-gray-400 hover:text-red-600"><Trash2 size={15} /></button>
                </td>
              </tr>
            ))}
            {orders.length === 0 && (
              <tr><td colSpan={7} className="py-8 text-center text-gray-400">No orders yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <OrderFormModal onClose={() => setShowCreate(false)} onSaved={() => { setShowCreate(false); load(); }} />
      )}
      {editOrder && (
        <OrderFormModal order={editOrder} onClose={() => setEditOrder(null)} onSaved={() => { setEditOrder(null); load(); }} />
      )}
      {viewOrder && (
        <OrderDetailModal order={viewOrder} onClose={() => setViewOrder(null)} isResearcher={isResearcher} onSaved={() => { setViewOrder(null); load(); }} />
      )}

      <ConfirmModal
        open={deleteId !== null}
        title="Delete order"
        message={`Confirm delete order #${deleteId}?`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
        danger
      />
    </div>
  );
}
