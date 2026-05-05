import { useEffect, useState } from "react";
import { solutionsApi, type DatasetStats } from "@/api/client";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer,
} from "recharts";
import { RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";

// ── helpers ───────────────────────────────────────────────────────────────────

const METHOD_LABEL: Record<string, string> = {
  greedy: "Greedy + ALNS",
  regret: "Regret-k + ALNS",
};

const DATASET_LABEL: Record<string, string> = {
  sartori: "Sartori & Buriol",
  lilim: "Li & Lim",
};

const METHOD_COLORS: Record<string, string> = {
  greedy: "#3b82f6",
  regret: "#a855f7",
};

function fmt(v: number | null | undefined, dec = 2): string {
  if (v == null) return "—";
  return v.toFixed(dec);
}

// ── Metric rows config ────────────────────────────────────────────────────────

interface MetricDef {
  key: keyof DatasetStats;
  labelKey: string;
  format: (v: number | null | undefined) => string;
  isGap?: boolean;
}

const METRICS: MetricDef[] = [
  { key: "count",            labelKey: "comparison.metricsLabels.count",           format: (v) => v?.toFixed(0) ?? "—" },
  { key: "avg_nv",           labelKey: "comparison.metricsLabels.avg_nv",          format: (v) => fmt(v, 2) },
  { key: "avg_cost",         labelKey: "comparison.metricsLabels.avg_cost",        format: (v) => fmt(v, 1) },
  { key: "avg_init_cost",    labelKey: "comparison.metricsLabels.avg_init_cost",   format: (v) => fmt(v, 1) },
  { key: "avg_improve_pct",  labelKey: "comparison.metricsLabels.avg_improve_pct", format: (v) => v != null ? `${v.toFixed(2)}%` : "—" },
  { key: "avg_gap_nv_pct",   labelKey: "comparison.metricsLabels.avg_gap_nv_pct",  format: (v) => v != null ? `+${v.toFixed(2)}%` : "—", isGap: true },
  { key: "avg_gap_cost_pct", labelKey: "comparison.metricsLabels.avg_gap_cost_pct", format: (v) => v != null ? `+${v.toFixed(2)}%` : "—", isGap: true },
  { key: "avg_elapsed_sec",  labelKey: "comparison.metricsLabels.avg_elapsed_sec", format: (v) => fmt(v, 2) },
  { key: "avg_iterations",   labelKey: "comparison.metricsLabels.avg_iterations",  format: (v) => v != null ? Math.round(v).toLocaleString() : "—" },
  { key: "avg_iter_per_sec", labelKey: "comparison.metricsLabels.avg_iter_per_sec", format: (v) => fmt(v, 1) },
];

// ── Radar normalizer ──────────────────────────────────────────────────────────

function buildRadarData(rows: DatasetStats[], t: (key: string) => string) {
  const axes = [
    { labelKey: "comparison.radarAxes.nv",      key: "avg_nv" as const,           invert: true },
    { labelKey: "comparison.radarAxes.cost",     key: "avg_cost" as const,         invert: true },
    { labelKey: "comparison.radarAxes.improve",  key: "avg_improve_pct" as const,  invert: false },
    { labelKey: "comparison.radarAxes.gap",      key: "avg_gap_cost_pct" as const, invert: true },
    { labelKey: "comparison.radarAxes.speed",    key: "avg_iter_per_sec" as const, invert: false },
  ];

  return axes.map(({ labelKey, key, invert }) => {
    const vals = rows.map((r) => r[key] as number | null).filter((v): v is number => v != null);
    const min = vals.length ? Math.min(...vals) : 0;
    const max = vals.length ? Math.max(...vals) : 1;
    const range = max - min || 1;

    const entry: Record<string, number | string> = { axis: t(labelKey) };
    rows.forEach((r) => {
      const raw = r[key] as number | null;
      if (raw == null) { entry[`${r.method}`] = 0; return; }
      const norm = (raw - min) / range * 100;
      entry[`${r.method}`] = invert ? 100 - norm : norm;
    });
    return entry;
  });
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ComparisonPage() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<DatasetStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeDataset, setActiveDataset] = useState<string>("all");

  const load = () => {
    setLoading(true);
    solutionsApi.stats()
      .then((r) => setStats(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const getDatasetLabel = (ds: string) => DATASET_LABEL[ds] ?? t("comparison.datasetOther");

  const datasets = ["all", ...Array.from(new Set(stats.map((s) => s.dataset)))];

  const filtered = activeDataset === "all"
    ? stats
    : stats.filter((s) => s.dataset === activeDataset);

  const methods = Array.from(new Set(filtered.map((s) => s.method)));

  // Bar chart data — one bar group per dataset
  const barDataNV = Array.from(new Set(filtered.map((s) => s.dataset))).map((ds) => {
    const entry: Record<string, string | number> = { dataset: getDatasetLabel(ds) };
    filtered.filter((s) => s.dataset === ds).forEach((s) => {
      entry[s.method] = s.avg_nv;
    });
    return entry;
  });

  const barDataCost = Array.from(new Set(filtered.map((s) => s.dataset))).map((ds) => {
    const entry: Record<string, string | number> = { dataset: getDatasetLabel(ds) };
    filtered.filter((s) => s.dataset === ds).forEach((s) => {
      entry[s.method] = +s.avg_cost.toFixed(1);
    });
    return entry;
  });

  const radarData = buildRadarData(filtered, t);

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
      {t("common.loadingData")}
    </div>
  );

  if (stats.length === 0) return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t("comparison.title")}</h1>
        <p className="text-sm text-gray-500 mt-0.5">{t("comparison.subtitle")}</p>
      </div>
      <div className="bg-white rounded-xl border border-gray-100 p-10 text-center">
        <p className="text-gray-400 text-sm">{t("comparison.noData")}</p>
      </div>
    </div>
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t("comparison.title")}</h1>
          <p className="text-sm text-gray-500 mt-0.5">{t("comparison.subtitle")}</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          <RefreshCw size={14} /> {t("btn.refresh")}
        </button>
      </div>

      {/* Dataset filter */}
      <div className="flex gap-2 mb-6">
        {datasets.map((ds) => (
          <button
            key={ds}
            onClick={() => setActiveDataset(ds)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
              activeDataset === ds
                ? "bg-blue-600 text-white"
                : "bg-white border border-gray-200 text-gray-600 hover:border-gray-300"
            }`}
          >
            {ds === "all" ? t("common.all") : getDatasetLabel(ds)}
          </button>
        ))}
      </div>

      {/* ── Comparison table ── */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm mb-6 overflow-x-auto">
        <div className="px-5 py-3 border-b">
          <h2 className="text-sm font-semibold text-gray-800">{t("comparison.tableTitle")}</h2>
          <p className="text-xs text-gray-400 mt-0.5">{t("comparison.tableSubtitle")}</p>
        </div>
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-gray-50 text-left">
              <th className="px-3 py-2.5 text-gray-600 font-medium w-56">{t("comparison.colCriteria")}</th>
              {filtered.map((s) => (
                <th key={`${s.dataset}-${s.method}`} className="px-3 py-2.5 text-center font-medium text-gray-700">
                  <span className="block text-xs text-gray-400">{getDatasetLabel(s.dataset)}</span>
                  <span className="block" style={{ color: METHOD_COLORS[s.method] ?? "#6b7280" }}>
                    {METHOD_LABEL[s.method] ?? s.method}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {METRICS.map((m) => (
              <tr key={m.key} className="hover:bg-gray-50">
                <td className="px-3 py-2 text-gray-600 font-medium">{t(m.labelKey)}</td>
                {filtered.map((s) => {
                  const val = s[m.key] as number | null;
                  if (m.isGap) return (
                    <td key={`${s.dataset}-${s.method}`} className="px-3 py-2 text-center">
                      {val != null ? (
                        <span className={`font-semibold ${val <= 1 ? "text-green-600" : val <= 5 ? "text-yellow-600" : "text-red-600"}`}>
                          +{val.toFixed(2)}%
                        </span>
                      ) : "—"}
                    </td>
                  );
                  return (
                    <td key={`${s.dataset}-${s.method}`} className="px-3 py-2 text-center text-gray-700">
                      {m.format(val)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Charts ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">

        {/* Bar: avg NV */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-gray-800 mb-4">{t("comparison.chartNV")}</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={barDataNV} margin={{ top: 0, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="dataset" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => (typeof v === "number" ? v.toFixed(2) : v)} />
              <Legend formatter={(v) => METHOD_LABEL[v] ?? v} />
              {methods.map((m) => (
                <Bar key={m} dataKey={m} fill={METHOD_COLORS[m] ?? "#9ca3af"} radius={[3, 3, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Bar: avg cost */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-gray-800 mb-4">{t("comparison.chartCost")}</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={barDataCost} margin={{ top: 0, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="dataset" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => (typeof v === "number" ? v.toFixed(1) : v)} />
              <Legend formatter={(v) => METHOD_LABEL[v] ?? v} />
              {methods.map((m) => (
                <Bar key={m} dataKey={m} fill={METHOD_COLORS[m] ?? "#9ca3af"} radius={[3, 3, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Radar chart */}
      {filtered.length >= 2 && (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-gray-800 mb-1">{t("comparison.radarTitle")}</h3>
          <p className="text-xs text-gray-400 mb-4">{t("comparison.radarDesc")}</p>
          <ResponsiveContainer width="100%" height={320}>
            <RadarChart data={radarData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
              <PolarGrid />
              <PolarAngleAxis dataKey="axis" tick={{ fontSize: 11 }} />
              <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 9 }} />
              {methods.map((m) => (
                <Radar
                  key={m}
                  name={METHOD_LABEL[m] ?? m}
                  dataKey={m}
                  stroke={METHOD_COLORS[m] ?? "#9ca3af"}
                  fill={METHOD_COLORS[m] ?? "#9ca3af"}
                  fillOpacity={0.15}
                />
              ))}
              <Legend formatter={(v) => METHOD_LABEL[v] ?? v} />
              <Tooltip formatter={(v) => (typeof v === "number" ? v.toFixed(1) : v)} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
