import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { instancesApi, solutionsApi, type BksEntry, type NodeCoord, type SolutionOut } from "@/api/client";
import { useJobPoller } from "@/components/JobStatusPoller";
import MapView, { ROUTE_COLORS } from "@/components/MapView";
import StatusBadge from "@/components/StatusBadge";
import { ArrowLeft, TrendingDown, Minus } from "lucide-react";
import { useTranslation } from "react-i18next";

const METHOD_LABEL: Record<string, string> = {
  greedy: "Greedy + ALNS",
  regret: "Regret-k + ALNS",
};

function fmt(v: number | null | undefined, decimals = 1): string {
  if (v == null) return "—";
  return v.toFixed(decimals);
}

function GapBadge({ pct }: { pct: number }) {
  if (pct < 0.01) return <span className="text-xs font-semibold text-green-600 bg-green-50 px-2 py-0.5 rounded-full">= BKS</span>;
  if (pct <= 5) return <span className="text-xs font-semibold text-yellow-700 bg-yellow-50 px-2 py-0.5 rounded-full">+{pct.toFixed(2)}%</span>;
  return <span className="text-xs font-semibold text-red-600 bg-red-50 px-2 py-0.5 rounded-full">+{pct.toFixed(2)}%</span>;
}

function MetricRow({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
      <span className="text-xs text-gray-500">{label}</span>
      <div className="text-right">
        <span className="text-sm font-semibold text-gray-800">{value}</span>
        {sub && <span className="text-xs text-gray-400 ml-1">{sub}</span>}
      </div>
    </div>
  );
}

export default function JobDetailPage() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const jobId = Number(id);
  const navigate = useNavigate();
  const [solution, setSolution] = useState<SolutionOut | null>(null);
  const [nodeCoords, setNodeCoords] = useState<NodeCoord[]>([]);
  const [solutionError, setSolutionError] = useState<string | null>(null);
  const [activeRouteIndex, setActiveRouteIndex] = useState<number | null>(null);
  const [bks, setBks] = useState<BksEntry | null | undefined>(undefined); // undefined=loading

  const loadSolution = (instanceName: string) => {
    setSolutionError(null);
    solutionsApi.byJob(jobId)
      .then((r) => {
        setSolution(r.data);
        instancesApi.nodes(instanceName)
          .then((nr) => setNodeCoords(nr.data.nodes))
          .catch(() => {});
        // Load BKS
        solutionsApi.bks(instanceName)
          .then((br) => setBks(br.data))
          .catch(() => setBks(null));
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail ?? err?.message ?? t("jobDetail.unknownError");
        setSolutionError(detail);
      });
  };

  const job = useJobPoller({
    jobId,
    onDone: (j) => { if (j.status === "done") loadSolution(j.instance_name); },
  });

  useEffect(() => {
    if (job?.status === "done") loadSolution(job.instance_name);
  }, [job?.status, jobId]);

  const mapNodes = useMemo(() =>
    nodeCoords.map((n) => ({ id: n.id, lat: n.lat, lng: n.lon, type: n.type, pair: n.pair })),
    [nodeCoords]
  );

  const mapCenter = useMemo<[number, number]>(() => {
    if (mapNodes.length === 0) return [21.028, 105.834];
    const lat = mapNodes.reduce((s, n) => s + n.lat, 0) / mapNodes.length;
    const lng = mapNodes.reduce((s, n) => s + n.lng, 0) / mapNodes.length;
    return [lat, lng];
  }, [mapNodes]);

  // Derived metrics
  // For Li&Lim: display total_distance; for Sartori/others: display total_cost (or fallback to total_distance)
  const displayCost = solution
    ? (solution.dataset_type === "lilim"
        ? solution.total_distance
        : (solution.total_cost ?? solution.total_distance))
    : null;
  const costLabel = solution?.dataset_type === "lilim"
    ? t("jobDetail.kpiDistance")
    : t("jobDetail.kpiCost");

  const improvePct = solution?.init_cost && solution.init_cost > 0 && displayCost != null
    ? ((solution.init_cost - displayCost) / solution.init_cost * 100)
    : null;

  const gapCostPct = bks && bks.bks_cost > 0 && displayCost != null
    ? ((displayCost - bks.bks_cost) / bks.bks_cost * 100)
    : null;

  const gapNvPct = bks && bks.bks_nv > 0
    ? ((solution!.num_vehicles - bks.bks_nv) / bks.bks_nv * 100)
    : null;

  const iterPerSec = solution?.iterations && solution.elapsed_sec && solution.elapsed_sec > 0
    ? solution.iterations / solution.elapsed_sec
    : null;

  const msPerIter = solution?.iterations && solution.elapsed_sec
    ? (solution.elapsed_sec / solution.iterations * 1000)
    : null;

  const actualElapsed = job?.started_at && job?.finished_at
    ? (new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000
    : null;

  if (!job) return <p className="text-gray-400 py-8">{t("jobDetail.loading")}</p>;

  return (
    <div className="max-w-5xl">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4">
        <ArrowLeft size={16} /> {t("btn.back")}
      </button>

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Job #{job.id}</h1>
        <StatusBadge status={job.status} />
      </div>

      {/* Job info */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 mb-4 grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
        <div><p className="text-gray-500">{t("jobDetail.colInstance")}</p><p className="font-mono font-medium">{job.instance_name}</p></div>
        <div><p className="text-gray-500">{t("jobDetail.colMethod")}</p><p className="font-medium">{METHOD_LABEL[job.method] ?? job.method}</p></div>
        <div><p className="text-gray-500">{t("jobDetail.colTimeLimit")}</p><p className="font-medium">{job.time_limit_sec}s</p></div>
        <div><p className="text-gray-500">{t("jobDetail.colSeed")}</p><p className="font-medium">{job.seed}</p></div>
        <div><p className="text-gray-500">{t("jobDetail.colCreatedAt")}</p><p>{new Date(job.created_at).toLocaleString()}</p></div>
        {job.finished_at && (
          <div><p className="text-gray-500">{t("jobDetail.colFinishedAt")}</p><p>{new Date(job.finished_at).toLocaleString()}</p></div>
        )}
      </div>

      {job.status === "running" && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-center gap-3 mb-4">
          <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-blue-700">{t("jobDetail.runningMsg")}</p>
        </div>
      )}
      {job.status === "failed" && job.error_msg && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-4">
          <p className="text-sm font-medium text-red-700 mb-1">{t("jobDetail.errorLabel")}</p>
          <pre className="text-xs text-red-600 whitespace-pre-wrap">{job.error_msg}</pre>
        </div>
      )}
      {solutionError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-4">
          <p className="text-sm font-medium text-red-700 mb-1">{t("jobDetail.solutionError")}</p>
          <pre className="text-xs text-red-600 whitespace-pre-wrap">{solutionError}</pre>
        </div>
      )}

      {solution && (
        <>
          {/* ── KPI cards ── */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            <div className="bg-white rounded-xl border border-gray-100 p-4 text-center">
              <p className="text-xs text-gray-500 mb-1">{t("jobDetail.kpiVehicles")}</p>
              <p className="text-3xl font-bold text-blue-600">{solution.num_vehicles}</p>
              {bks && <p className="text-xs text-gray-400 mt-1">{t("jobDetail.bksLabel")} {bks.bks_nv} {t("jobDetail.bksVehicles")}</p>}
            </div>
            <div className="bg-white rounded-xl border border-gray-100 p-4 text-center">
              <p className="text-xs text-gray-500 mb-1">{costLabel}</p>
              <p className="text-3xl font-bold text-green-600">{displayCost != null ? displayCost.toFixed(1) : "—"}</p>
              {bks && <p className="text-xs text-gray-400 mt-1">{t("jobDetail.bksLabel")} {bks.bks_cost.toFixed(1)}</p>}
            </div>
            <div className="bg-white rounded-xl border border-gray-100 p-4 text-center">
              <p className="text-xs text-gray-500 mb-1">{t("jobDetail.kpiImprove")}</p>
              {improvePct != null ? (
                <>
                  <p className="text-3xl font-bold text-purple-600">{improvePct.toFixed(1)}%</p>
                  <p className="text-xs text-gray-400 mt-1">{t("jobDetail.initLabel")} {solution.init_cost?.toFixed(1)}</p>
                </>
              ) : <p className="text-2xl font-bold text-gray-300">—</p>}
            </div>
            <div className="bg-white rounded-xl border border-gray-100 p-4 text-center">
              <p className="text-xs text-gray-500 mb-1">{t("jobDetail.kpiIterations")}</p>
              <p className="text-3xl font-bold text-orange-500">{solution.iterations?.toLocaleString() ?? "—"}</p>
              {iterPerSec != null && <p className="text-xs text-gray-400 mt-1">{iterPerSec.toFixed(0)} {t("jobDetail.iterPerSec")}</p>}
            </div>
          </div>

          {/* ── 3 side panels ── */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">

            {/* Gap vs BKS */}
            <div className="bg-white rounded-xl border border-gray-100 p-4">
              <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-3">
                {t("jobDetail.sectionGap")}
              </h3>
              {bks === undefined ? (
                <p className="text-xs text-gray-400">{t("jobDetail.bksLookingUp")}</p>
              ) : bks === null ? (
                <p className="text-xs text-gray-400 italic">{t("jobDetail.bksNone")}</p>
              ) : (
                <>
                  <MetricRow
                    label={t("jobDetail.gapNV")}
                    value={gapNvPct != null ? <GapBadge pct={gapNvPct} /> : "—"}
                  />
                  <MetricRow
                    label={t("jobDetail.gapCost")}
                    value={gapCostPct != null ? <GapBadge pct={gapCostPct} /> : "—"}
                  />
                  <MetricRow label={t("jobDetail.bksNV")} value={bks.bks_nv} />
                  <MetricRow label={t("jobDetail.bksCost")} value={bks.bks_cost.toFixed(1)} />
                  <MetricRow label={t("jobDetail.bksSource")} value={bks.reference} />
                  <MetricRow label={t("jobDetail.bksDate")} value={bks.date} />
                </>
              )}
            </div>

            {/* Performance */}
            <div className="bg-white rounded-xl border border-gray-100 p-4">
              <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-3">
                {t("jobDetail.sectionPerf")}
              </h3>
              <MetricRow label={t("jobDetail.perfRunTime")} value={fmt(solution.elapsed_sec, 2)} sub={t("jobDetail.perfRunTimeSub")} />
              <MetricRow label={t("jobDetail.perfTotalTime")} value={fmt(actualElapsed, 2)} sub={t("jobDetail.perfTotalTimeSub")} />
              <MetricRow label={t("jobDetail.perfIterations")} value={solution.iterations?.toLocaleString() ?? "—"} />
              <MetricRow label={t("jobDetail.perfSpeed")} value={fmt(iterPerSec, 1)} sub={t("jobDetail.perfSpeedSub")} />
              <MetricRow label={t("jobDetail.perfMsPerIter")} value={fmt(msPerIter, 3)} sub={t("jobDetail.perfMsPerIterSub")} />
              <MetricRow label={t("jobDetail.perfInitSol")} value={fmt(solution.init_cost, 1)} sub={`(${solution.init_nv ?? "?"} xe)`} />
              <MetricRow label={t("jobDetail.perfFinalSol")} value={fmt(displayCost, 1)} sub={`(${solution.num_vehicles} xe)`} />
              {improvePct != null && (
                <MetricRow
                  label={t("jobDetail.perfAlnsImprove")}
                  value={
                    <span className={improvePct > 0 ? "text-green-600" : "text-gray-400"}>
                      {improvePct > 0 ? <TrendingDown size={12} className="inline mr-1" /> : <Minus size={12} className="inline mr-1" />}
                      {improvePct.toFixed(2)}%
                    </span>
                  }
                />
              )}
            </div>

            {/* Environment */}
            <div className="bg-white rounded-xl border border-gray-100 p-4">
              <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-3">
                {t("jobDetail.sectionEnv")}
              </h3>
              <MetricRow label={t("jobDetail.envRunner")} value={job.owner_id ? `#${job.owner_id}` : "—"} />
              <MetricRow label={t("jobDetail.envHostname")} value={solution.hostname ?? "—"} />
              <MetricRow label={t("jobDetail.envOS")} value={
                <span className="text-xs text-right leading-snug max-w-[140px] block">{solution.os_info ?? "—"}</span>
              } />
              <MetricRow label={t("jobDetail.envCPU")} value={
                <span className="text-xs text-right leading-snug max-w-[140px] block">{solution.cpu_info ?? "—"}</span>
              } />
              <MetricRow label={t("jobDetail.envRAM")} value={solution.ram_gb != null ? `${solution.ram_gb} GB` : "—"} />
              <MetricRow label={t("jobDetail.envCPUUsage")} value={solution.cpu_usage_pct != null ? `${solution.cpu_usage_pct}%` : "—"} />
            </div>
          </div>

          {/* ── Map + route list ── */}
          <div className="flex flex-col lg:flex-row gap-4 mb-4">
            <div className="flex-1 h-96 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
              {mapNodes.length > 0 ? (
                <MapView
                  routes={solution.routes}
                  nodes={mapNodes}
                  center={mapCenter}
                  zoom={12}
                  activeRouteIndex={activeRouteIndex}
                  onRouteHover={setActiveRouteIndex}
                />
              ) : (
                <div className="h-full flex items-center justify-center text-gray-400 text-sm">{t("jobDetail.mapLoading")}</div>
              )}
            </div>
            <div className="w-full lg:w-72 bg-white rounded-xl shadow-sm border border-gray-100 p-4 overflow-y-auto max-h-96">
              <h3 className="font-semibold text-gray-900 text-sm mb-3">
                {t("jobDetail.routesTitle", { count: solution.routes.length })}
              </h3>
              <div className="space-y-1">
                {solution.routes.map((r, ri) => {
                  const color = ROUTE_COLORS[ri % ROUTE_COLORS.length];
                  const isActive = activeRouteIndex === r.route_index;
                  return (
                    <div
                      key={r.route_index}
                      className={`rounded-lg px-2 py-1.5 -mx-2 cursor-default transition-colors ${isActive ? "bg-red-50" : "hover:bg-gray-50"}`}
                      onMouseEnter={() => setActiveRouteIndex(r.route_index)}
                      onMouseLeave={() => setActiveRouteIndex(null)}
                    >
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: isActive ? "red" : color }} />
                        <span className={`text-xs font-semibold ${isActive ? "text-red-600" : "text-gray-700"}`}>
                          Route {r.route_index}
                        </span>
                        <span className="text-xs text-gray-400 ml-auto">{r.stops.length} stops</span>
                      </div>
                      <p className="text-xs font-mono text-gray-400 pl-4 leading-relaxed">
                        {r.stops.map((s) => s.node_id).join(" ")}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Solution file format */}
          <div className="bg-gray-900 rounded-xl p-4 text-xs font-mono text-gray-100 overflow-x-auto">
            <p className="text-gray-400 mb-2 font-sans text-xs">{t("jobDetail.solutionFileComment")}</p>
            <p>Instance name : {job.instance_name}</p>
            <p>Solution</p>
            {solution.routes.map((r) => (
              <p key={r.route_index}>Route {r.route_index} : {r.stops.map((s) => s.node_id).join(" ")}</p>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
