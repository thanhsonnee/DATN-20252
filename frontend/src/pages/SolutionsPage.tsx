import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { solutionsApi, type SolutionOut } from "@/api/client";
import { Eye } from "lucide-react";
import { useTranslation } from "react-i18next";

export default function SolutionsPage() {
  const { t } = useTranslation();
  const [solutions, setSolutions] = useState<SolutionOut[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    solutionsApi.list().then((r) => setSolutions(r.data)).finally(() => setLoading(false));
  }, []);

  // Best solution per instance: fewest vehicles, then lowest distance
  const bestIds = new Set<number>();
  const byInstance: Record<string, SolutionOut[]> = {};
  for (const s of solutions) {
    (byInstance[s.instance_name] ??= []).push(s);
  }
  for (const group of Object.values(byInstance)) {
    const best = group.reduce((a, b) => {
      if (a.num_vehicles < b.num_vehicles) return a;
      if (a.num_vehicles === b.num_vehicles && a.total_distance < b.total_distance) return a;
      return b;
    });
    bestIds.add(best.id);
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t("solutions.title")}</h1>
        <p className="text-sm text-gray-500">{t("solutions.subtitle")}</p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        {loading ? (
          <p className="text-center text-gray-400 py-8">{t("solutions.loading")}</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b">
                <th className="pb-2 pr-4">{t("solutions.colId")}</th>
                <th className="pb-2 pr-4">{t("solutions.colInstance")}</th>
                <th className="pb-2 pr-4">{t("solutions.colMethod")}</th>
                <th className="pb-2 pr-4">{t("solutions.colVehicles")}</th>
                <th className="pb-2 pr-4">{t("solutions.colDistance")}</th>
                <th className="pb-2 pr-4">{t("solutions.colJob")}</th>
                <th className="pb-2 pr-4">{t("solutions.colCreatedAt")}</th>
                <th className="pb-2"></th>
              </tr>
            </thead>
            <tbody>
              {solutions.map((s) => {
                const isBest = bestIds.has(s.id);
                return (
                  <tr
                    key={s.id}
                    className={`border-b last:border-0 hover:bg-gray-50 ${isBest ? "bg-green-50" : ""}`}
                  >
                    <td className="py-2 pr-4 text-gray-500">
                      #{s.id}
                      {isBest && <span className="ml-1 text-xs text-green-600 font-semibold">★</span>}
                    </td>
                    <td className="py-2 pr-4 font-mono font-medium">{s.instance_name}</td>
                    <td className="py-2 pr-4 uppercase text-xs font-medium">{s.method}</td>
                    <td className="py-2 pr-4 font-semibold text-blue-700">{s.num_vehicles}</td>
                    <td className="py-2 pr-4 font-semibold text-green-700">{s.total_distance.toFixed(1)}</td>
                    <td className="py-2 pr-4 text-gray-500">
                      <button
                        onClick={() => navigate(`/jobs/${s.job_id}`)}
                        className="hover:underline hover:text-blue-600"
                      >
                        #{s.job_id}
                      </button>
                    </td>
                    <td className="py-2 pr-4 text-gray-500">{new Date(s.created_at).toLocaleString()}</td>
                    <td className="py-2 text-right">
                      <button
                        onClick={() => navigate(`/solutions/${s.id}`)}
                        className="p-1 text-gray-400 hover:text-blue-600"
                        title={t("solutions.tooltipView")}
                      >
                        <Eye size={16} />
                      </button>
                    </td>
                  </tr>
                );
              })}
              {solutions.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-gray-400">
                    {t("solutions.noSolutions")}{" "}<strong>{t("solutions.noSolutionsSuffix")}</strong>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
