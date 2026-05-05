import React from "react";
import { useTranslation } from "react-i18next";

const MAP: Record<string, string> = {
  pending:     "bg-yellow-100 text-yellow-800",
  running:     "bg-blue-100 text-blue-800",
  done:        "bg-green-100 text-green-800",
  failed:      "bg-red-100 text-red-800",
  available:   "bg-green-100 text-green-800",
  in_use:      "bg-blue-100 text-blue-800",
  maintenance: "bg-orange-100 text-orange-800",
  confirmed:   "bg-purple-100 text-purple-800",
  in_transit:  "bg-cyan-100 text-cyan-800",
  delivered:   "bg-green-100 text-green-800",
  cancelled:   "bg-gray-100 text-gray-600",
};

export default function StatusBadge({ status }: { status: string }) {
  const { t } = useTranslation();
  const labelKey = `statusBadge.${status}`;
  const label = t(labelKey, { defaultValue: status });

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${MAP[status] ?? "bg-gray-100 text-gray-600"}`}>
      {label}
    </span>
  );
}
