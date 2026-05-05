import React, { useState } from "react";
import toast from "react-hot-toast";
import { ordersApi, type OrderOut, type OrderStatus } from "@/api/client";
import StatusBadge from "@/components/StatusBadge";
import { X } from "lucide-react";

const STATUS_FLOW: OrderStatus[] = ["pending", "confirmed", "in_transit", "delivered", "cancelled"];
const STATUS_LABEL: Record<OrderStatus, string> = {
  pending: "Pending",
  confirmed: "Confirmed",
  in_transit: "In Transit",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

interface Props {
  order: OrderOut;
  isResearcher: boolean;
  onClose: () => void;
  onSaved: () => void;
}

export default function OrderDetailModal({ order, isResearcher, onClose, onSaved }: Props) {
  const [status, setStatus] = useState<OrderStatus>(order.status);
  const [saving, setSaving] = useState(false);

  const handleStatusChange = async (newStatus: OrderStatus) => {
    setSaving(true);
    try {
      await ordersApi.update(order.id, { status: newStatus });
      setStatus(newStatus);
      toast.success("Status updated");
      onSaved();
    } catch (e: any) {
      toast.error(e.response?.data?.detail ?? "Error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl p-6 max-w-lg w-full mx-4">
        <div className="flex justify-between items-start mb-4">
          <h3 className="font-semibold text-gray-900 text-lg">Order #{order.id}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700"><X size={18} /></button>
        </div>

        <div className="space-y-3 text-sm mb-4">
          <div className="flex justify-between">
            <span className="text-gray-500">Status</span>
            <StatusBadge status={status} />
          </div>
          <div>
            <p className="text-gray-500 mb-0.5">Pickup address</p>
            <p className="font-medium">{order.pickup_address}</p>
          </div>
          <div>
            <p className="text-gray-500 mb-0.5">Delivery address</p>
            <p className="font-medium">{order.delivery_address}</p>
          </div>
          {(order.time_window_start || order.time_window_end) && (
            <div className="flex justify-between">
              <span className="text-gray-500">Time window</span>
              <span>{order.time_window_start} – {order.time_window_end}</span>
            </div>
          )}
          {order.description && (
            <div>
              <p className="text-gray-500 mb-0.5">Notes</p>
              <p>{order.description}</p>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-gray-500">Created</span>
            <span>{new Date(order.created_at).toLocaleString()}</span>
          </div>
        </div>

        {/* Dispatcher can change status */}
        {isResearcher && (
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">Update status:</p>
            <div className="flex flex-wrap gap-2">
              {STATUS_FLOW.map((s) => (
                <button
                  key={s}
                  disabled={s === status || saving}
                  onClick={() => handleStatusChange(s)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium border transition-colors ${
                    s === status
                      ? "bg-blue-100 text-blue-700 border-blue-300"
                      : "border-gray-300 hover:bg-gray-50 text-gray-600"
                  } disabled:opacity-50`}
                >
                  {STATUS_LABEL[s]}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-end mt-6">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
