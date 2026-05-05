import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { jobsApi, type JobOut } from "@/api/client";
import StatusBadge from "@/components/StatusBadge";
import ConfirmModal from "@/components/ConfirmModal";
import { Plus, Trash2, Eye, RefreshCw, Download } from "lucide-react";
import { useTranslation } from "react-i18next";

export default function JobsPage() {
  const { t } = useTranslation();
  const [jobs, setJobs] = useState<JobOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const navigate = useNavigate();

  // ID of the best done job (fewest vehicles, then lowest distance)
  const bestJobId = jobs
    .filter((j) => j.status === "done" && j.solution)
    .reduce<JobOut | null>((best, j) => {
      if (!best || !best.solution) return j;
      if (j.solution!.num_vehicles < best.solution.num_vehicles) return j;
      if (
        j.solution!.num_vehicles === best.solution.num_vehicles &&
        j.solution!.total_distance < best.solution.total_distance
      ) return j;
      return best;
    }, null)?.id ?? null;

  const load = () => {
    setLoading(true);
    jobsApi.list().then((r) => setJobs(r.data)).finally(() => setLoading(false));
  };

  const handleExport = async () => {
    try {
      const res = await jobsApi.exportExcel();
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = "jobs_export.xlsx";
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error("Export failed");
    }
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await jobsApi.delete(deleteId);
      toast.success(t("jobs.deleteSuccess"));
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail ?? t("jobs.deleteFailed"));
    } finally {
      setDeleteId(null);
    }
  };

  const duration = (j: JobOut) => {
    if (!j.started_at || !j.finished_at) return "—";
    const s = (new Date(j.finished_at).getTime() - new Date(j.started_at).getTime()) / 1000;
    return `${s.toFixed(1)}s`;
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t("jobs.title")}</h1>
          <p className="text-sm text-gray-500">{t("jobs.subtitle")}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="p-2 rounded-lg border border-gray-300 hover:bg-gray-50">
            <RefreshCw size={16} />
          </button>
          <button
            onClick={handleExport}
            className="inline-flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
          >
            <Download size={16} /> Export Excel
          </button>
          <Link
            to="/jobs/new"
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
          >
            <Plus size={16} /> {t("jobs.newJob")}
          </Link>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        {loading ? (
          <p className="text-center text-gray-400 py-8">{t("common.loading")}</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b">
                <th className="pb-2">{t("jobs.colId")}</th>
                <th className="pb-2">{t("jobs.colInstance")}</th>
                <th className="pb-2">{t("jobs.colMethod")}</th>
                <th className="pb-2">{t("jobs.colTimeLimit")}</th>
                <th className="pb-2">{t("jobs.colStatus")}</th>
                <th className="pb-2">{t("jobs.colDuration")}</th>
                <th className="pb-2">{t("jobs.colVehicles")}</th>
                <th className="pb-2">Distance / Cost</th>
                <th className="pb-2">{t("jobs.colCreatedAt")}</th>
                <th className="pb-2"></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr
                  key={j.id}
                  className={`border-b last:border-0 hover:bg-gray-50 ${j.id === bestJobId ? "bg-green-50" : ""}`}
                >
                  <td className="py-2 text-gray-500">
                    #{j.id}
                    {j.id === bestJobId && (
                      <span className="ml-1 text-xs text-green-600 font-semibold">★</span>
                    )}
                  </td>
                  <td className="py-2 font-mono font-medium">{j.instance_name}</td>
                  <td className="py-2 uppercase text-xs font-medium">{j.method}</td>
                  <td className="py-2">{j.time_limit_sec}s</td>
                  <td className="py-2"><StatusBadge status={j.status} /></td>
                  <td className="py-2">{duration(j)}</td>
                  <td className="py-2 font-medium">{j.solution ? j.solution.num_vehicles : "—"}</td>
                  <td className="py-2">
                    {j.solution
                      ? j.solution.dataset_type === "lilim"
                        ? `${j.solution.total_distance.toFixed(1)} dist`
                        : j.solution.total_cost != null
                          ? `${j.solution.total_cost.toFixed(1)} cost`
                          : `${j.solution.total_distance.toFixed(1)}`
                      : "—"}
                  </td>
                  <td className="py-2 text-gray-500">{new Date(j.created_at).toLocaleString()}</td>
                  <td className="py-2 flex gap-1 justify-end">
                    <button
                      onClick={() => navigate(`/jobs/${j.id}`)}
                      className="p-1 text-gray-400 hover:text-blue-600"
                    >
                      <Eye size={16} />
                    </button>
                    <button
                      onClick={() => setDeleteId(j.id)}
                      className="p-1 text-gray-400 hover:text-red-600"
                      disabled={j.status === "running"}
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
              {jobs.length === 0 && (
                <tr><td colSpan={10} className="py-8 text-center text-gray-400">{t("jobs.noJobs")}</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      <ConfirmModal
        open={deleteId !== null}
        title={t("jobs.deleteTitle")}
        message={t("jobs.deleteMsg", { id: deleteId })}
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
        danger
      />
    </div>
  );
}
