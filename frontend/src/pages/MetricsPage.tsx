import React, { useEffect, useRef, useState } from "react";
import { Upload, Trash2, Lock, CheckCircle, Globe, Users, Settings2 } from "lucide-react";
import toast from "react-hot-toast";
import { metricsApi, visibilityApi, uploadAnalyzeApi, type MetricOut, type LLMAnalysis, type AnalyzeResponse } from "@/api/client";
import VisibilityModal from "@/components/VisibilityModal";
import LLMAnalysisReview from "@/components/LLMAnalysisReview";
import { useAuth } from "@/contexts/AuthContext";
import { useTranslation } from "react-i18next";

function VisibilityBadge({ v }: { v: string }) {
  const { t } = useTranslation();
  if (v === "private")
    return <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-500"><Lock size={9} /> {t("visibility.private")}</span>;
  if (v === "shared")
    return <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-blue-50 text-blue-600"><Users size={9} /> {t("visibility.shared")}</span>;
  return <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-green-50 text-green-600"><Globe size={9} /> {t("visibility.public")}</span>;
}

const PLUGIN_TEMPLATE = `# RouteX Metric Plugin Template
# Required functions: get_name(), get_description(), compute()

def get_name() -> str:
    return "My Custom Metric"


def get_description() -> str:
    return "Describe your metric here."


def compute(solution, instance, **kwargs) -> float:
    """
    Args:
        solution: solver.models.Solution
        instance: solver.models.Instance
    Returns:
        float — metric value
    """
    raise NotImplementedError("Implement your metric here")
`;

export default function MetricsPage() {
  const { t } = useTranslation();
  const { isMetricProvider, isAdmin, user } = useAuth();
  const [metrics, setMetrics] = useState<MetricOut[]>([]);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  // Visibility modal state
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [editMetric, setEditMetric] = useState<MetricOut | null>(null);
  const [visibility, setVisibility] = useState("public");
  const [sharedWith, setSharedWith] = useState<string[]>([]);
  // LLM analysis state
  const [llmResult, setLlmResult] = useState<AnalyzeResponse | null>(null);
  const [llmAnalysis, setLlmAnalysis] = useState<LLMAnalysis | null>(null);

  const load = () =>
    metricsApi.list().then((r) => setMetrics(r.data)).catch(() => {});

  useEffect(() => { load(); }, []);

  const handleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPendingFile(file);
    setVisibility("public");
    setSharedWith([]);
  };

  const doUpload = async (vis: string, emails: string[]) => {
    if (!pendingFile) return;
    setPendingFile(null);
    setAnalyzing(true);
    try {
      const res = await uploadAnalyzeApi.metric(pendingFile, vis, emails);
      setLlmResult(res.data);
      setLlmAnalysis(res.data.analysis);
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? t("metrics.uploadFailed"));
    } finally {
      setAnalyzing(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleLLMConfirm = async () => {
    if (!llmResult || !llmAnalysis) return;
    setUploading(true);
    try {
      await uploadAnalyzeApi.confirm(llmResult.temp_id, "metric", llmAnalysis);
      toast.success(t("metrics.uploadSuccess"));
      load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? t("metrics.uploadFailed"));
    } finally {
      setUploading(false);
      setLlmResult(null);
      setLlmAnalysis(null);
    }
  };

  const handleLLMReject = async () => {
    if (!llmResult) return;
    try {
      await uploadAnalyzeApi.reject("metric", llmResult.temp_id);
    } catch {}
    setLlmResult(null);
    setLlmAnalysis(null);
  };

  const handleEditVisibility = async (vis: string, emails: string[]) => {
    if (!editMetric) return;
    try {
      await visibilityApi.updateMetric(editMetric.id, vis, emails);
      toast.success(t("metrics.visUpdateSuccess"));
      load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? t("metrics.visUpdateFailed"));
    } finally {
      setEditMetric(null);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await metricsApi.delete(id);
      toast.success(t("metrics.deleteSuccess"));
      load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? t("metrics.deleteFailed"));
    } finally {
      setDeleteId(null);
    }
  };

  // Map DB metric name → i18n key
  const SYSTEM_METRIC_KEY: Record<string, string> = {
    "Number of Vehicles (NV)":   "nv",
    "Gap NV (%)":                "gapNv",
    "Best (instances)":          "best",
    "CPU Time (s)":              "cpuTime",
    "ALNS Iterations":           "alnsIter",
    "Iterations/second":         "iterPerSec",
    "Total Distance (TD)":       "td",
    "Gap TD (%)":                "gapTd",
    "Improvement TD (%)":        "improveTd",
    "Total Cost":                "cost",
    "Gap Cost (%)":              "gapCost",
    "Improvement Cost (%)":      "improveCost",
  };

  // Which DB metric names belong to which group
  const GROUP_COMMON  = ["Number of Vehicles (NV)", "Gap NV (%)", "Best (instances)", "CPU Time (s)", "ALNS Iterations", "Iterations/second"];
  const GROUP_LILIM   = ["Total Distance (TD)", "Gap TD (%)", "Improvement TD (%)"];
  const GROUP_SARTORI = ["Total Cost", "Gap Cost (%)", "Improvement Cost (%)"];

  const tMetricName = (m: MetricOut) => {
    if (!m.is_system) return m.name;
    const key = SYSTEM_METRIC_KEY[m.name];
    return key ? t(`metrics.sysName.${key}`) : m.name;
  };

  const tMetricDesc = (m: MetricOut) => {
    if (!m.is_system) return m.description ?? "—";
    const key = SYSTEM_METRIC_KEY[m.name];
    return key ? t(`metrics.sysDesc.${key}`) : (m.description ?? "—");
  };

  const systemMetrics = metrics.filter((m) => m.is_system);
  const userMetrics   = metrics.filter((m) => !m.is_system);

  const byGroup = (names: string[]) =>
    systemMetrics.filter((m) => names.includes(m.name));

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t("metrics.title")}</h1>
          <p className="text-sm text-gray-500 mt-0.5">{t("metrics.subtitle")}</p>
        </div>
        {isMetricProvider && (
          <div>
            <input ref={fileRef} type="file" accept=".py" className="hidden" onChange={handleUpload} />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              <Upload size={16} /> {uploading ? t("btn.uploading") : t("btn.uploadMetric")}
            </button>
          </div>
        )}
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
        {[
          { label: t("metrics.cardCommon"), value: byGroup(GROUP_COMMON).length },
          { label: t("metrics.cardCustom"), value: userMetrics.length },
          { label: t("metrics.cardTotal"),  value: metrics.length },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 text-center">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className="text-2xl font-bold text-gray-800 mt-0.5">{s.value}</p>
          </div>
        ))}
      </div>

      {/* System metrics — grouped by dataset */}
      {([
        {
          titleKey: "metrics.groupCommon",
          headerCls: "bg-blue-50 border-blue-100",
          textCls: "text-blue-700",
          badgeCls: "bg-blue-100 text-blue-600",
          iconCls: "text-blue-400",
          items: byGroup(GROUP_COMMON),
        },
        {
          titleKey: "metrics.groupLilim",
          headerCls: "bg-purple-50 border-purple-100",
          textCls: "text-purple-700",
          badgeCls: "bg-purple-100 text-purple-600",
          iconCls: "text-purple-400",
          items: byGroup(GROUP_LILIM),
        },
        {
          titleKey: "metrics.groupSartori",
          headerCls: "bg-amber-50 border-amber-100",
          textCls: "text-amber-700",
          badgeCls: "bg-amber-100 text-amber-600",
          iconCls: "text-amber-400",
          items: byGroup(GROUP_SARTORI),
        },
      ] as const).map(({ titleKey, headerCls, textCls, badgeCls, iconCls, items }) => (
        <div key={titleKey} className="bg-white rounded-xl border border-gray-100 shadow-sm mb-3">
          <div className={`flex items-center gap-2 px-5 py-3 border-b rounded-t-xl ${headerCls}`}>
            <Lock size={13} className={iconCls} />
            <h3 className={`text-sm font-semibold ${textCls}`}>{t(titleKey)}</h3>
            <span className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium ${badgeCls}`}>
              {items.length}
            </span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b">
                <th className="py-2 pl-5 w-8"></th>
                <th className="py-2 w-56">{t("metrics.colName")}</th>
                <th className="py-2 pr-5">{t("metrics.colDesc")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((m) => (
                <tr key={m.id} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="py-2.5 pl-5">
                    <CheckCircle size={14} className="text-green-500" />
                  </td>
                  <td className="py-2.5 font-medium text-gray-800 pr-4">{tMetricName(m)}</td>
                  <td className="py-2.5 text-xs text-gray-500 pr-5">{tMetricDesc(m)}</td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={3} className="py-4 text-center text-gray-300 text-xs">{t("metrics.noSystemMetrics")}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      ))}

      {/* User-uploaded metrics */}
      {(userMetrics.length > 0 || isMetricProvider) && (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm mb-4">
          <div className="px-5 py-3 border-b">
            <h3 className="text-sm font-semibold text-gray-700">{t("metrics.customSection")}</h3>
          </div>
          {userMetrics.length === 0 ? (
            <div className="py-8 text-center text-gray-400 text-sm">
              {t("metrics.noCustomMetrics")}
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 border-b">
                  <th className="py-2 pl-5">{t("metrics.colName")}</th>
                  <th className="py-2">{t("metrics.colDesc")}</th>
                  <th className="py-2">{t("metrics.colVisibility")}</th>
                  <th className="py-2">{t("metrics.colFile")}</th>
                  <th className="py-2">{t("metrics.colCreatedAt")}</th>
                  <th className="py-2 pr-5"></th>
                </tr>
              </thead>
              <tbody>
                {userMetrics.map((m) => (
                  <tr key={m.id} className="border-b last:border-0 hover:bg-gray-50">
                    <td className="py-2 pl-5 font-medium text-gray-800">{m.name}</td>
                    <td className="py-2 text-gray-500 text-xs">{m.description ?? "—"}</td>
                    <td className="py-2"><VisibilityBadge v={m.visibility} /></td>
                    <td className="py-2 font-mono text-xs text-gray-400">{m.filename ?? "—"}</td>
                    <td className="py-2 text-gray-400 text-xs">{new Date(m.created_at).toLocaleDateString()}</td>
                    <td className="py-2 pr-5">
                      <div className="flex items-center gap-1">
                        {(isAdmin || m.uploaded_by_id === user?.user_id) && (
                          <button onClick={() => setEditMetric(m)} className="p-1 text-gray-300 hover:text-blue-500" title={t("metrics.tooltipEditVis")}>
                            <Settings2 size={15} />
                          </button>
                        )}
                        {(isAdmin || m.uploaded_by_id === user?.user_id) && (
                          <button onClick={() => setDeleteId(m.id)} className="p-1 text-gray-300 hover:text-red-500">
                            <Trash2 size={15} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Plugin interface guide */}
      {isMetricProvider && (
        <div className="mt-4 bg-purple-50 border border-purple-100 rounded-xl px-5 py-4">
          <p className="text-sm font-semibold text-purple-800 mb-2">{t("metrics.pluginGuideTitle")}</p>
          <pre className="text-xs text-purple-700 bg-purple-100 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">{PLUGIN_TEMPLATE}</pre>
        </div>
      )}

      {/* Confirm delete */}
      {deleteId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="font-semibold text-gray-900 mb-2">{t("metrics.deleteTitle")}</h3>
            <p className="text-sm text-gray-600 mb-4">{t("metrics.deleteMsg")}</p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setDeleteId(null)}
                className="px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50">{t("btn.cancel")}</button>
              <button onClick={() => handleDelete(deleteId)}
                className="px-4 py-2 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700">{t("btn.delete")}</button>
            </div>
          </div>
        </div>
      )}

      {pendingFile && (
        <VisibilityModal
          title={t("metrics.visModalTitle")}
          subtitle={`File: ${pendingFile.name}`}
          confirmLabel={analyzing ? t("btn.uploading") : t("btn.upload")}
          accentColor="purple"
          onConfirm={doUpload}
          onCancel={() => { setPendingFile(null); if (fileRef.current) fileRef.current.value = ""; }}
        />
      )}

      {/* Analyzing overlay */}
      {analyzing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl px-8 py-6 flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-gray-600">AI đang phân tích plugin...</p>
          </div>
        </div>
      )}

      {/* LLM analysis review modal */}
      {llmResult && llmAnalysis && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-xl mx-4 flex flex-col max-h-[90vh]">
            <div className="px-5 py-4 border-b">
              <h3 className="font-semibold text-gray-900">Xác nhận phân tích độ đo</h3>
              <p className="text-xs text-gray-500 mt-0.5">Kiểm tra và chỉnh sửa kết quả AI trước khi lưu</p>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-4">
              <LLMAnalysisReview
                analysis={llmAnalysis}
                onChange={setLlmAnalysis}
                llmAvailable={llmResult.llm_available}
                kind="metric"
              />
            </div>
            <div className="flex justify-between gap-3 px-5 py-4 border-t">
              <button onClick={handleLLMReject} disabled={uploading}
                className="px-4 py-2 text-sm rounded-lg border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50">
                Hủy upload
              </button>
              <button onClick={handleLLMConfirm} disabled={uploading}
                className="px-5 py-2 text-sm rounded-lg bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 font-medium">
                {uploading ? "Đang lưu..." : "Xác nhận & Lưu"}
              </button>
            </div>
          </div>
        </div>
      )}

      {editMetric && (
        <VisibilityModal
          title={t("metrics.visEditTitle")}
          subtitle={`${t("metrics.visEditSubtitlePrefix")} ${editMetric.name}`}
          initialVisibility={editMetric.visibility as any}
          confirmLabel={t("btn.save")}
          accentColor="purple"
          onConfirm={handleEditVisibility}
          onCancel={() => setEditMetric(null)}
        />
      )}
    </div>
  );
}
