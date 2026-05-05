import { useMemo, useEffect, useState } from "react";
import { MapContainer, TileLayer, Polyline, Marker } from "react-leaflet";
import L from "leaflet";
import type { RouteOut } from "@/api/client";

export const ROUTE_COLORS = [
  "#3775b2","#b1b945","#45b940","#953fbb","#64d65f","#396ced","#7e54d4","#529d21",
  "#da68e2","#8dc74e","#3447b4","#adc341","#4d58c9","#d1b837","#8d7ff3","#82a732",
  "#b273e8","#70c366","#cc3ca3","#3b953e","#a13ea2","#43b26a","#e2428a","#50cf92",
  "#e53657","#46cad2","#d93f23","#4b96eb","#e99a28","#3360bd","#c5992a","#4e45a3",
];

// ---------- node icon creators (inline style — no CSS injection needed) ----------

function mkPickupIcon(size: number, opaque: boolean): L.DivIcon {
  const op = opaque ? "0.3" : "1";
  return L.divIcon({
    className: "",
    html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:#db0f0f;border:2px solid #111;box-sizing:border-box;opacity:${op}"></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function mkDeliveryIcon(size: number, opaque: boolean): L.DivIcon {
  const half = Math.round(size / 2);
  const op = opaque ? "0.3" : "1";
  // Upward-pointing triangle via CSS border trick
  return L.divIcon({
    className: "",
    html: `<div style="opacity:${op};width:0;height:0;border-left:${half}px solid transparent;border-right:${half}px solid transparent;border-bottom:${size}px solid #227cab;"></div>`,
    iconSize: [size, size],
    iconAnchor: [half, Math.round(size * 0.6)],
  });
}

function mkDepotIcon(size: number, opaque: boolean): L.DivIcon {
  const op = opaque ? "0.3" : "1";
  return L.divIcon({
    className: "",
    html: `<div style="width:${size}px;height:${size}px;background:#111;border:2px solid #fff;box-sizing:border-box;opacity:${op}"></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

// ---------- interfaces ----------

export interface MapNode {
  id: number;
  lat: number;
  lng: number;
  type?: "depot" | "pickup" | "delivery";
  pair?: number | null;
}

interface Props {
  routes: RouteOut[];
  nodes: MapNode[];
  center?: [number, number];
  zoom?: number;
  /** Route index currently highlighted from outside (sidebar hover) */
  activeRouteIndex?: number | null;
  /** Notify parent which route is hovered on the map */
  onRouteHover?: (idx: number | null) => void;
}

// ---------- helpers ----------

function scaleAbstractNodes(nodes: MapNode[], center: [number, number]): MapNode[] {
  if (nodes.length === 0) return [];
  const lats = nodes.map((n) => n.lat);
  const lngs = nodes.map((n) => n.lng);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs), maxLng = Math.max(...lngs);
  const span = 0.06;
  return nodes.map((n) => ({
    ...n,
    lat: center[0] + ((n.lat - minLat) / (maxLat - minLat || 1) - 0.5) * span,
    lng: center[1] + ((n.lng - minLng) / (maxLng - minLng || 1) - 0.5) * span,
  }));
}

function isAbstractCoords(nodes: MapNode[]): boolean {
  const samples = nodes.filter((n) => n.type !== "depot").slice(0, 5);
  if (samples.length === 0) return false;
  // Real lat/lon always has meaningful decimal precision; abstract coords are integers < 500
  return samples.every((n) => Number.isInteger(n.lat) && Number.isInteger(n.lng) && Math.abs(n.lat) < 500);
}

async function fetchOsrmRoute(waypoints: [number, number][]): Promise<[number, number][]> {
  if (waypoints.length < 2) return waypoints;
  const coords = waypoints.map(([lat, lng]) => `${lng},${lat}`).join(";");
  const url = `https://router.project-osrm.org/route/v1/driving/${coords}?overview=full&geometries=geojson`;
  const res = await fetch(url);
  if (!res.ok) return waypoints;
  const data = await res.json();
  const geom = data?.routes?.[0]?.geometry?.coordinates;
  if (geom) return geom.map(([lng, lat]: [number, number]) => [lat, lng] as [number, number]);
  return waypoints;
}

// ---------- component ----------

export default function MapView({
  routes,
  nodes,
  center = [21.028, 105.834],
  zoom = 13,
  activeRouteIndex,
  onRouteHover,
}: Props) {
  const [mapHoveredRoute, setMapHoveredRoute] = useState<number | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<number | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);
  const [roadPaths, setRoadPaths] = useState<Map<number, [number, number][]>>(new Map());
  const [roadsLoading, setRoadsLoading] = useState(false);

  // ---- scale coords if abstract ----
  const { scaledNodes, mapCenter, useAbstract } = useMemo(() => {
    if (nodes.length === 0) return { scaledNodes: [], mapCenter: center, useAbstract: false };
    const abstract = isAbstractCoords(nodes);
    const scaled = abstract ? scaleAbstractNodes(nodes, center) : nodes;
    const realCenter: [number, number] = [
      scaled.reduce((s, n) => s + n.lat, 0) / scaled.length,
      scaled.reduce((s, n) => s + n.lng, 0) / scaled.length,
    ];
    return { scaledNodes: scaled, mapCenter: realCenter, useAbstract: abstract };
  }, [nodes, center]);

  const nodeMap = useMemo(() => new Map(scaledNodes.map((n) => [n.id, n])), [scaledNodes]);
  const depotNode = scaledNodes.find((n) => n.type === "depot") ?? nodeMap.get(0);

  // ---- highlight logic ----
  const highlightedRouteIndex = mapHoveredRoute ?? activeRouteIndex ?? null;

  // for node pair highlighting
  const hoveredNode = hoveredNodeId !== null ? nodeMap.get(hoveredNodeId) : null;
  const hoveredPairId = hoveredNode?.pair ?? null;

  // ---- straight-line waypoints (used as OSRM input) ----
  const routeWaypoints = useMemo(() =>
    routes.map((route, ri) => {
      const stops = route.stops.map((s) => nodeMap.get(s.node_id)).filter(Boolean) as MapNode[];
      const path: [number, number][] = [
        ...(depotNode ? [[depotNode.lat, depotNode.lng] as [number, number]] : []),
        ...stops.map((n) => [n.lat, n.lng] as [number, number]),
        ...(depotNode ? [[depotNode.lat, depotNode.lng] as [number, number]] : []),
      ];
      return { routeIndex: route.route_index, ri, path };
    }),
    [routes, nodeMap, depotNode]
  );

  // ---- road routing (OSRM) ----
  useEffect(() => {
    if (useAbstract || scaledNodes.length === 0 || routes.length === 0) {
      setRoadPaths(new Map());
      return;
    }

    let cancelled = false;
    setRoadPaths(new Map());
    setRoadsLoading(true);

    (async () => {
      const nm = new Map(scaledNodes.map((n) => [n.id, n]));
      const depot = scaledNodes.find((n) => n.type === "depot") ?? nm.get(0);

      const allRoutes = routes.map((route) => {
        const stops = route.stops.map((s) => nm.get(s.node_id)).filter(Boolean) as MapNode[];
        const path: [number, number][] = [
          ...(depot ? [[depot.lat, depot.lng] as [number, number]] : []),
          ...stops.map((n) => [n.lat, n.lng] as [number, number]),
          ...(depot ? [[depot.lat, depot.lng] as [number, number]] : []),
        ];
        return { routeIndex: route.route_index, path };
      });

      const results = await Promise.all(
        allRoutes.map(async ({ routeIndex, path }) => {
          try {
            const road = await fetchOsrmRoute(path);
            return [routeIndex, road] as const;
          } catch {
            return [routeIndex, path] as const;
          }
        })
      );

      if (!cancelled) {
        setRoadPaths(new Map(results));
        setRoadsLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [scaledNodes, routes, useAbstract]);

  // ---- render ----
  return (
    <div className="relative h-full w-full">
      {roadsLoading && (
        <div className="absolute inset-0 z-[1000] flex items-center justify-center pointer-events-none">
          <div className="bg-white/90 rounded-lg px-3 py-1.5 text-xs text-gray-600 shadow flex items-center gap-2">
            <div className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            Loading actual route...
          </div>
        </div>
      )}
    <MapContainer center={mapCenter} zoom={zoom} className="h-full w-full">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {/* For abstract coords (Li&Lim): straight-line polylines since coords aren't real */}
      {useAbstract && routeWaypoints.map(({ routeIndex, ri, path }) => {
        const color = ROUTE_COLORS[ri % ROUTE_COLORS.length];
        const isHighlighted = highlightedRouteIndex === routeIndex;
        const isFaded = highlightedRouteIndex !== null && !isHighlighted;
        return (
          <Polyline
            key={`line-${routeIndex}`}
            positions={path}
            pathOptions={{
              color: isHighlighted ? "#e53935" : color,
              weight: isHighlighted ? 4 : 2,
              opacity: isFaded ? 0.2 : 0.85,
            }}
            eventHandlers={{
              mouseover: () => { setMapHoveredRoute(routeIndex); onRouteHover?.(routeIndex); },
              mouseout: () => { setMapHoveredRoute(null); onRouteHover?.(null); },
            }}
          />
        );
      })}

      {/* For real coords (Sartori): OSRM road polylines only */}
      {!useAbstract && routeWaypoints.map(({ routeIndex, ri }) => {
        const color = ROUTE_COLORS[ri % ROUTE_COLORS.length];
        const isHighlighted = highlightedRouteIndex === routeIndex;
        const isFaded = highlightedRouteIndex !== null && !isHighlighted;
        const roadPath = roadPaths.get(routeIndex);
        if (!roadPath) return null;
        return (
          <Polyline
            key={`road-${routeIndex}`}
            positions={roadPath}
            pathOptions={{
              color: isHighlighted ? "#e53935" : color,
              weight: isHighlighted ? 5 : 2.5,
              opacity: isFaded ? 0.2 : 0.9,
            }}
            eventHandlers={{
              mouseover: () => { setMapHoveredRoute(routeIndex); onRouteHover?.(routeIndex); },
              mouseout: () => { setMapHoveredRoute(null); onRouteHover?.(null); },
            }}
          />
        );
      })}

      {/* Node markers: red circle = pickup, blue triangle = delivery, black square = depot */}
      {scaledNodes.map((node) => {
        const isActive = hoveredNodeId === node.id || hoveredPairId === node.id;
        const isOpaque = hoveredNodeId !== null && !isActive;
        const baseSize = node.type === "depot" ? 12 : 10;
        const size = isActive ? baseSize * 1.8 : baseSize;

        let icon: L.DivIcon;
        if (node.type === "delivery") icon = mkDeliveryIcon(size, isOpaque);
        else if (node.type === "depot") icon = mkDepotIcon(size, isOpaque);
        else icon = mkPickupIcon(size, isOpaque);

        return (
          <Marker
            key={`n-${node.id}`}
            position={[node.lat, node.lng]}
            icon={icon}
            zIndexOffset={isActive ? 1000 : 0}
            eventHandlers={{
              mouseover: (e) => {
                setHoveredNodeId(node.id);
                const { clientX, clientY } = e.originalEvent;
                setTooltipPos({ x: clientX, y: clientY });
              },
              mousemove: (e) => {
                const { clientX, clientY } = e.originalEvent;
                setTooltipPos({ x: clientX, y: clientY });
              },
              mouseout: () => {
                setHoveredNodeId(null);
                setTooltipPos(null);
              },
            }}
          />
        );
      })}
    </MapContainer>

      {/* Floating tooltip — rendered outside Leaflet to avoid sticky-tooltip bug */}
      {tooltipPos && hoveredNodeId !== null && (() => {
        const node = nodeMap.get(hoveredNodeId);
        if (!node) return null;
        const label = node.type === "pickup" ? "Pickup" : node.type === "delivery" ? "Delivery" : "Depot";
        return (
          <div
            style={{
              position: "fixed",
              left: tooltipPos.x + 12,
              top: tooltipPos.y - 28,
              pointerEvents: "none",
              zIndex: 9999,
            }}
            className="bg-white border border-gray-300 rounded px-2 py-1 text-xs shadow-md whitespace-nowrap"
          >
            <strong>{label} {node.id}</strong>
            {node.pair != null && ` ↔ ${node.type === "pickup" ? "Delivery" : "Pickup"} ${node.pair}`}
          </div>
        );
      })()}
    </div>
  );
}
