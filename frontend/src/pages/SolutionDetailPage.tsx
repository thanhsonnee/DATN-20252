import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { instancesApi, solutionsApi, type NodeCoord, type SolutionOut } from "@/api/client";
import MapView from "@/components/MapView";
import { ArrowLeft } from "lucide-react";
import { useTranslation } from "react-i18next";

const COLORS = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"];

/** Fallback: place nodes on a circle when real coords are unavailable */
function circleCoords(nodeIds: number[]): NodeCoord[] {
  const center = { lat: 21.028, lng: 105.834 };
  const radius = 0.04;
  return nodeIds.map((id, i) => {
    const angle = (i / nodeIds.length) * 2 * Math.PI;
    return { id, lat: center.lat + radius * Math.sin(angle), lon: center.lng + radius * Math.cos(angle) };
  });
}

export default function SolutionDetailPage() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [solution, setSolution] = useState<SolutionOut | null>(null);
  const [nodeCoords, setNodeCoords] = useState<NodeCoord[]>([]);

  useEffect(() => {
    solutionsApi.get(Number(id)).then((r) => {
      const sol = r.data;
      setSolution(sol);
      // Fetch real coordinates for this instance
      instancesApi.nodes(sol.instance_name)
        .then((nr) => setNodeCoords(nr.data.nodes))
        .catch(() => {
          // Fallback to circle layout if instance file not accessible
          const allIds = new Set<number>();
          sol.routes.forEach((r) => r.stops.forEach((s) => allIds.add(s.node_id)));
          setNodeCoords(circleCoords(Array.from(allIds).sort((a, b) => a - b)));
        });
    }).catch(() => {});
  }, [id]);

  // Build MapView-compatible nodes array (lat/lng naming)
  const mapNodes = useMemo(() =>
    nodeCoords.map((n) => ({ id: n.id, lat: n.lat, lng: n.lon, label: `Node ${n.id}` })),
    [nodeCoords]
  );

  // Compute map center from node coordinates
  const center = useMemo<[number, number]>(() => {
    if (mapNodes.length === 0) return [21.028, 105.834];
    const lat = mapNodes.reduce((s, n) => s + n.lat, 0) / mapNodes.length;
    const lng = mapNodes.reduce((s, n) => s + n.lng, 0) / mapNodes.length;
    return [lat, lng];
  }, [mapNodes]);

  if (!solution) return <p className="text-gray-400 py-8">{t("solutionDetail.loading")}</p>;

  const methodLabel = solution.method === "regret" ? "Regret-k + ALNS" : "Greedy + ALNS";

  return (
    <div>
      <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4">
        <ArrowLeft size={16} /> {t("btn.back")}
      </button>

      <div className="flex items-center gap-4 mb-2">
        <h1 className="text-2xl font-bold text-gray-900">Solution #{solution.id}</h1>
        <span className="text-sm text-gray-400">Job #{solution.job_id}</span>
      </div>
      <div className="flex gap-3 mb-5 text-sm text-gray-600">
        <span className="font-mono font-semibold text-gray-800">{solution.instance_name}</span>
        <span className="text-gray-400">|</span>
        <span>{methodLabel}</span>
      </div>

      {/* KPI bar */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="bg-white rounded-xl border border-gray-100 p-4 text-center">
          <p className="text-xs text-gray-500 mb-1">{t("solutionDetail.kpiVehicles")}</p>
          <p className="text-3xl font-bold text-blue-600">{solution.num_vehicles}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-4 text-center">
          <p className="text-xs text-gray-500 mb-1">{t("solutionDetail.kpiDistance")}</p>
          <p className="text-3xl font-bold text-green-600">{solution.total_distance.toFixed(1)}</p>
        </div>
      </div>

      {/* Map + route table side by side */}
      <div className="flex flex-col lg:flex-row gap-4">
        <div className="flex-1 h-96 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {mapNodes.length > 0 ? (
            <MapView routes={solution.routes} nodes={mapNodes} center={center} zoom={12} />
          ) : (
            <div className="h-full flex items-center justify-center text-gray-400 text-sm">{t("solutionDetail.mapLoading")}</div>
          )}
        </div>

        <div className="w-full lg:w-80 bg-white rounded-xl shadow-sm border border-gray-100 p-4 overflow-y-auto max-h-96">
          <h3 className="font-semibold text-gray-900 text-sm mb-3">
            {t("solutionDetail.routesTitle", { count: solution.routes.length })}
          </h3>
          <div className="space-y-3">
            {solution.routes.map((r, ri) => (
              <div key={r.route_index}>
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className="w-3 h-3 rounded-full flex-shrink-0"
                    style={{ background: COLORS[ri % COLORS.length] }}
                  />
                  <span className="text-xs font-semibold text-gray-700">
                    Route {r.route_index} — {r.stops.length} {t("solutionDetail.stopCount")}
                  </span>
                </div>
                <p className="text-xs font-mono text-gray-500 pl-5 leading-relaxed">
                  0 → {r.stops.map((s) => s.node_id).join(" → ")} → 0
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
