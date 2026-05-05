import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { jobsApi, type JobOut } from "@/api/client";
import { useAuth } from "@/contexts/AuthContext";
import StatusBadge from "@/components/StatusBadge";
import { PlayCircle } from "lucide-react";
import { useTranslation } from "react-i18next";

export default function DashboardPage() {
  const { t } = useTranslation();
  const { user, isAlgoTester } = useAuth();
  const [jobs, setJobs] = useState<JobOut[]>([]);

  useEffect(() => {
    if (isAlgoTester) {
      jobsApi.list().then((r) => setJobs(r.data)).catch(() => {});
    }
  }, [isAlgoTester]);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-1">{t("dashboard.title")}</h1>
      <p className="text-sm text-gray-500 mb-6">{t("dashboard.greeting", { name: user?.full_name })}</p>

      {isAlgoTester && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
            <div className="bg-white rounded-xl shadow-sm p-5 flex items-center gap-4 border border-gray-100">
              <div className="p-2 rounded-lg text-blue-600 bg-blue-50">
                <PlayCircle size={22} />
              </div>
              <div>
                <p className="text-xs text-gray-500">{t("dashboard.jobsRun")}</p>
                <p className="text-2xl font-bold text-gray-900">{jobs.length}</p>
              </div>
            </div>
            <div className="bg-white rounded-xl shadow-sm p-5 flex items-center gap-4 border border-gray-100">
              <div className="p-2 rounded-lg text-green-600 bg-green-50">
                <PlayCircle size={22} />
              </div>
              <div>
                <p className="text-xs text-gray-500">{t("dashboard.jobsDone")}</p>
                <p className="text-2xl font-bold text-gray-900">{jobs.filter((j) => j.status === "done").length}</p>
              </div>
            </div>
            <div className="bg-white rounded-xl shadow-sm p-5 flex items-center gap-4 border border-gray-100">
              <div className="p-2 rounded-lg text-red-600 bg-red-50">
                <PlayCircle size={22} />
              </div>
              <div>
                <p className="text-xs text-gray-500">{t("dashboard.jobsFailed")}</p>
                <p className="text-2xl font-bold text-gray-900">{jobs.filter((j) => j.status === "failed").length}</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <div className="flex justify-between items-center mb-4">
              <h2 className="font-semibold text-gray-900">{t("dashboard.recentJobs")}</h2>
              <Link to="/jobs" className="text-xs text-blue-600 hover:underline">{t("dashboard.viewAll", { defaultValue: t("btn.viewAll") })}</Link>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 border-b">
                  <th className="pb-2">{t("dashboard.colId")}</th>
                  <th className="pb-2">{t("dashboard.colInstance")}</th>
                  <th className="pb-2">{t("dashboard.colMethod")}</th>
                  <th className="pb-2">{t("dashboard.colStatus")}</th>
                  <th className="pb-2">{t("dashboard.colTime")}</th>
                </tr>
              </thead>
              <tbody>
                {jobs.slice(0, 5).map((j) => (
                  <tr key={j.id} className="border-b last:border-0">
                    <td className="py-2 text-gray-500">#{j.id}</td>
                    <td className="py-2 font-medium">{j.instance_name}</td>
                    <td className="py-2 uppercase text-xs">{j.method}</td>
                    <td className="py-2"><StatusBadge status={j.status} /></td>
                    <td className="py-2 text-gray-500">{new Date(j.created_at).toLocaleString()}</td>
                  </tr>
                ))}
                {jobs.length === 0 && (
                  <tr><td colSpan={5} className="py-6 text-center text-gray-400">{t("dashboard.noJobs")}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {!isAlgoTester && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-10 text-center text-gray-400">
          <p className="text-lg font-medium">{t("dashboard.welcome")}</p>
          <p className="text-sm mt-1">{t("dashboard.welcomeSub")}</p>
        </div>
      )}
    </div>
  );
}
