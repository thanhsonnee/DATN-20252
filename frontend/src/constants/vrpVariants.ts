export const VRP_VARIANTS = [
  { key: "PDPTW", label: "PDPTW", desc: "Pickup & Delivery with Time Windows" },
  { key: "2E-VRP", label: "2E-VRP", desc: "Two-Echelon Vehicle Routing" },
];

/** Which dataset labels are valid test beds for each VRP variant. */
export const VARIANT_DATASET_LABELS: Record<string, string[]> = {
  "PDPTW":  ["Li & Lim", "Ropke-Cordeau", "Sartori & Buriol"],
  "2E-VRP": ["2E-EVRP", "2E-VRP-PDD"],
};

export const DATASET_FORMAT_OPTIONS = [
  "Li & Lim",
  "Ropke-Cordeau",
  "Sartori & Buriol",
  "2E-EVRP",
  "2E-VRP-PDD",
  "N/A",
];

export type MetricDef = {
  key: string;
  label: string;
  unit: string;
  better: "lower" | "higher";
  desc: string;
};

export const VARIANT_METRICS: Record<string, MetricDef[]> = {
  PDPTW: [
    { key: "total_distance",  label: "Total Distance",              unit: "",   better: "lower",  desc: "Total travel cost across all routes" },
    { key: "num_vehicles",    label: "Vehicles Used",               unit: "",   better: "lower",  desc: "Number of vehicles with at least 1 stop" },
    { key: "elapsed_sec",     label: "Runtime",                     unit: "s",  better: "lower",  desc: "Total solver runtime" },
    { key: "iterations",      label: "Iterations",                  unit: "",   better: "higher", desc: "Number of ALNS iterations within the time limit" },
    { key: "init_cost",       label: "Initial Cost",                unit: "",   better: "lower",  desc: "Total cost of initial solution before ALNS" },
    { key: "improve_pct",     label: "Gap vs BKS",                  unit: "%",  better: "lower",  desc: "% deviation from best-known solution" },
  ],
  VRPTW: [
    { key: "total_distance",  label: "Total Distance",              unit: "",   better: "lower",  desc: "Total travel cost across all routes" },
    { key: "num_vehicles",    label: "Vehicles Used",               unit: "",   better: "lower",  desc: "Number of vehicles used" },
    { key: "elapsed_sec",     label: "Runtime",                     unit: "s",  better: "lower",  desc: "Total solver runtime" },
    { key: "improve_pct",     label: "Gap vs BKS",                  unit: "%",  better: "lower",  desc: "% deviation from best-known solution" },
  ],
  CVRP: [
    { key: "total_distance",  label: "Total Distance",              unit: "",   better: "lower",  desc: "Total travel cost across all routes" },
    { key: "num_vehicles",    label: "Vehicles Used",               unit: "",   better: "lower",  desc: "Number of vehicles used" },
    { key: "elapsed_sec",     label: "Runtime",                     unit: "s",  better: "lower",  desc: "Total solver runtime" },
  ],
  VRP: [
    { key: "total_distance",  label: "Total Distance",              unit: "",   better: "lower",  desc: "Total travel cost across all routes" },
    { key: "num_vehicles",    label: "Vehicles Used",               unit: "",   better: "lower",  desc: "Number of vehicles used" },
    { key: "elapsed_sec",     label: "Runtime",                     unit: "s",  better: "lower",  desc: "Total solver runtime" },
  ],
};
