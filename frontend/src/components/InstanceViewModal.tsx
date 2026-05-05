import { useEffect, useRef, useState } from "react";
import { instancesApi, type InstanceInfo, type ParseReport, type ParseFieldStatus } from "@/api/client";
import { X, PlayCircle, Search } from "lucide-react";
import { useTranslation } from "react-i18next";

interface Props {
  path: string | null;
  instanceName: string;
  instanceInfo?: InstanceInfo | null;
  onClose: () => void;
  onRun: (name: string) => void;
}

type Tab = "content" | "report";

const STATUS_CONFIG_KEYS: Record<ParseFieldStatus, { labelKey: string; bg: string; text: string; dot: string }> = {
  ok:      { labelKey: "instanceViewModal.statusOk",      bg: "bg-green-50",  text: "text-green-700",  dot: "bg-green-500" },
  derived: { labelKey: "instanceViewModal.statusDerived",  bg: "bg-yellow-50", text: "text-yellow-700", dot: "bg-yellow-500" },
  ignored: { labelKey: "instanceViewModal.statusIgnored",  bg: "bg-gray-50",   text: "text-gray-500",   dot: "bg-gray-400" },
  error:   { labelKey: "instanceViewModal.statusError",    bg: "bg-red-50",    text: "text-red-700",    dot: "bg-red-500" },
};

const DATASET_BADGE: Record<string, string> = {
  sartori:       "bg-blue-100 text-blue-700",
  lilim:         "bg-purple-100 text-purple-700",
  ropke_cordeau: "bg-orange-100 text-orange-700",
  "2e_vrp_pdd":  "bg-teal-100 text-teal-700",
  "2e_evrp":     "bg-indigo-100 text-indigo-700",
};

/** Wrap matched substring in a <mark> span, return array of React nodes */
function highlight(text: string, query: string): React.ReactNode {
  if (!query) return text;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-yellow-200 rounded-sm px-0.5">{text.slice(idx, idx + query.length)}</mark>
      {highlight(text.slice(idx + query.length), query)}
    </>
  );
}

export default function InstanceViewModal({ path, instanceName, instanceInfo, onClose, onRun }: Props) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("report");
  const [content, setContent] = useState<string | null>(null);
  const [report, setReport] = useState<ParseReport | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [loadingReport, setLoadingReport] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!path) return;
    setContent(null);
    setReport(null);
    setError(null);
    setSearch("");

    setLoadingReport(true);
    instancesApi
      .parseReport(instanceName)
      .then((r) => setReport(r.data))
      .catch(() => setError(t("instanceViewModal.errorParseReport")))
      .finally(() => setLoadingReport(false));
  }, [path, instanceName]);

  const loadContent = () => {
    if (content || loadingContent || !path) return;
    setLoadingContent(true);
    instancesApi
      .content(path)
      .then((r) => setContent(r.data.content))
      .catch(() => setError(t("instanceViewModal.errorReadFile")))
      .finally(() => setLoadingContent(false));
  };

  const handleTabChange = (t: Tab) => {
    setTab(t);
    setSearch("");
    if (t === "content") loadContent();
    setTimeout(() => searchRef.current?.focus(), 50);
  };

  if (!path) return null;

  const q = search.trim().toLowerCase();

  // Group report fields by category
  const grouped = report
    ? report.fields.reduce<Record<string, typeof report.fields>>((acc, f) => {
        (acc[f.category] ??= []).push(f);
        return acc;
      }, {})
    : {};

  // Filter grouped by search query
  const filteredGrouped: typeof grouped = {};
  if (report) {
    for (const [cat, fields] of Object.entries(grouped)) {
      const matches = q
        ? fields.filter((f) =>
            [f.field, f.source, f.value, f.note, cat].some((v) =>
              v.toLowerCase().includes(q)
            )
          )
        : fields;
      if (matches.length > 0) filteredGrouped[cat] = matches;
    }
  }

  // Highlight content lines containing query
  const contentLines = content?.split("\n") ?? [];
  const matchedLineCount = q
    ? contentLines.filter((l) => l.toLowerCase().includes(q)).length
    : 0;

  const uploadedAt = instanceInfo?.uploaded_at
    ? new Date(instanceInfo.uploaded_at).toLocaleString()
    : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl mx-4 flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="min-w-0">
              <h3 className="font-semibold text-gray-900 font-mono text-sm truncate">{instanceName}</h3>
              <p className="text-xs text-gray-400 mt-0.5 truncate">{path}</p>
            </div>
            {report && (
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full shrink-0 ${DATASET_BADGE[report.dataset_type] ?? "bg-gray-100 text-gray-600"}`}>
                {report.dataset_type_label}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0 ml-3">
            <button
              onClick={() => onRun(instanceName)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
            >
              <PlayCircle size={15} /> {t("btn.run")}
            </button>
            <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100">
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Upload info bar */}
        {(instanceInfo?.uploaded_by || uploadedAt) && (
          <div className="px-5 py-2 bg-gray-50 border-b flex items-center gap-4 text-xs text-gray-500">
            {instanceInfo?.uploaded_by && (
              <span>{t("instanceViewModal.uploadedBy")} <span className="font-medium text-gray-700">{instanceInfo.uploaded_by}</span></span>
            )}
            {uploadedAt && (
              <span>{t("instanceViewModal.uploadedAt")} <span className="font-medium text-gray-700">{uploadedAt}</span></span>
            )}
          </div>
        )}

        {/* Tabs + Search bar */}
        <div className="flex items-center border-b shrink-0 px-5 gap-4">
          <div className="flex">
            {(["report", "content"] as Tab[]).map((tabKey) => (
              <button
                key={tabKey}
                onClick={() => handleTabChange(tabKey)}
                className={`py-2.5 px-4 text-sm font-medium border-b-2 -mb-px transition-colors ${
                  tab === tabKey
                    ? "border-blue-500 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                {tabKey === "report" ? t("instanceViewModal.tabReport") : t("instanceViewModal.tabContent")}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="flex-1 flex items-center gap-2 py-2">
            <div className="relative flex-1 max-w-xs">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                ref={searchRef}
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t("instanceViewModal.searchPlaceholder")}
                className="w-full pl-7 pr-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
            {q && (
              <span className="text-xs text-gray-400 shrink-0">
                {tab === "content"
                  ? t("instanceViewModal.matchedLines", { count: matchedLineCount })
                  : t("instanceViewModal.matchedFields", { count: Object.values(filteredGrouped).flat().length })}
              </span>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="overflow-auto flex-1 p-5">
          {error && <p className="text-center text-red-500 py-8">{error}</p>}

          {/* ── Parse Report tab ── */}
          {tab === "report" && !error && (
            <>
              {loadingReport && <p className="text-center text-gray-400 py-8">{t("instanceViewModal.loadingReport")}</p>}
              {report && (
                <div className="space-y-5">
                  {/* Stats */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {[
                      { label: "Nodes", value: report.stats.num_nodes ?? "—" },
                      { label: "Requests", value: report.stats.num_requests ?? "—" },
                      { label: "Capacity", value: report.stats.capacity ?? "—" },
                      { label: "Horizon", value: report.stats.horizon ?? "—" },
                    ].map((s) => (
                      <div key={s.label} className="bg-gray-50 rounded-lg p-3 text-center">
                        <p className="text-xs text-gray-500">{s.label}</p>
                        <p className="text-lg font-bold text-gray-800">{String(s.value)}</p>
                      </div>
                    ))}
                  </div>

                  {/* Errors */}
                  {report.errors.length > 0 && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                      <p className="text-sm font-semibold text-red-700 mb-2">{t("instanceViewModal.errorTitle")}</p>
                      <ul className="space-y-1">
                        {report.errors.map((e, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm text-red-600">
                            <span className="mt-0.5 shrink-0">✗</span>
                            <span>{highlight(e, search)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Warnings */}
                  {report.warnings.length > 0 && (
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                      <p className="text-sm font-semibold text-yellow-700 mb-2">{t("instanceViewModal.warningTitle")}</p>
                      <ul className="space-y-1">
                        {report.warnings.map((w, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm text-yellow-700">
                            <span className="mt-0.5 shrink-0">⚠</span>
                            <span>{highlight(w, search)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Legend */}
                  <div className="flex flex-wrap gap-3">
                    {(Object.entries(STATUS_CONFIG_KEYS) as [ParseFieldStatus, typeof STATUS_CONFIG_KEYS[ParseFieldStatus]][]).map(([k, v]) => (
                      <div key={k} className="flex items-center gap-1.5 text-xs text-gray-600">
                        <span className={`w-2 h-2 rounded-full ${v.dot}`} />
                        <span>{t(v.labelKey)}</span>
                      </div>
                    ))}
                  </div>

                  {/* Tables */}
                  {Object.keys(filteredGrouped).length === 0 && q && (
                    <p className="text-center text-gray-400 text-sm py-4">{t("instanceViewModal.noResults", { query: search })}</p>
                  )}
                  {Object.entries(filteredGrouped).map(([category, fields]) => (
                    <div key={category}>
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{category}</h4>
                      <div className="border border-gray-200 rounded-lg overflow-hidden">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="bg-gray-50 text-left text-xs text-gray-500">
                              <th className="px-3 py-2 font-medium w-8"></th>
                              <th className="px-3 py-2 font-medium">{t("instanceViewModal.colField")}</th>
                              <th className="px-3 py-2 font-medium">{t("instanceViewModal.colSource")}</th>
                              <th className="px-3 py-2 font-medium">{t("instanceViewModal.colSampleValue")}</th>
                              <th className="px-3 py-2 font-medium">{t("instanceViewModal.colNote")}</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-100">
                            {fields.map((f, i) => {
                              const cfg = STATUS_CONFIG_KEYS[f.status];
                              return (
                                <tr key={i} className={cfg.bg}>
                                  <td className="px-3 py-2">
                                    <span className={`w-2 h-2 rounded-full ${cfg.dot} block mx-auto`} />
                                  </td>
                                  <td className={`px-3 py-2 font-mono font-medium text-xs ${cfg.text}`}>
                                    {highlight(f.field, search)}
                                  </td>
                                  <td className="px-3 py-2 text-xs text-gray-500">{highlight(f.source, search)}</td>
                                  <td className="px-3 py-2 text-xs font-mono text-gray-600 max-w-[120px] truncate">
                                    {f.value ? highlight(f.value, search) : <span className="text-gray-300">—</span>}
                                  </td>
                                  <td className="px-3 py-2 text-xs text-gray-500">{highlight(f.note, search)}</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* ── Raw file tab ── */}
          {tab === "content" && !error && (
            <>
              {loadingContent && <p className="text-center text-gray-400 py-8">{t("instanceViewModal.loadingContent")}</p>}
              {content && (
                <pre className="text-xs font-mono text-gray-700 whitespace-pre leading-relaxed">
                  {contentLines.map((line, i) => {
                    const match = q && line.toLowerCase().includes(q);
                    return (
                      <div
                        key={i}
                        className={match ? "bg-yellow-50 -mx-5 px-5" : ""}
                      >
                        <span className="select-none text-gray-300 mr-4 text-right inline-block w-8">
                          {i + 1}
                        </span>
                        {match ? highlight(line, search) : line}
                        {"\n"}
                      </div>
                    );
                  })}
                </pre>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
