import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default api;

// ── Typed helpers ──────────────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    api.post<TokenResponse>("/auth/login", { email, password }),
  signup: (email: string, password: string, full_name?: string, role?: string) =>
    api.post("/auth/signup", { email, password, full_name, role }),
  verifyEmail: (token: string) =>
    api.get("/auth/verify-email", { params: { token } }),
  forgotPassword: (email: string) =>
    api.post("/auth/forgot-password", { email }),
  resetPassword: (token: string, new_password: string) =>
    api.post("/auth/reset-password", { token, new_password }),
  refreshToken: (refresh_token: string) =>
    api.post("/auth/refresh-token", { refresh_token }),
  logout: (refresh_token: string) =>
    api.post("/auth/logout", { refresh_token }),
};

export const usersApi = {
  me: () => api.get<UserOut>("/users/me"),
  list: () => api.get<UserOut[]>("/users/"),
  byEmail: (email: string) => api.get<UserOut>(`/users/by-email`, { params: { email } }),
  create: (data: UserCreate) => api.post<UserOut>("/users/", data),
  update: (id: number, data: Partial<UserCreate>) => api.patch<UserOut>(`/users/${id}`, data),
  delete: (id: number) => api.delete(`/users/${id}`),
};

export const fleetApi = {
  list: () => api.get<VehicleOut[]>("/fleet/"),
  create: (data: VehicleCreate) => api.post<VehicleOut>("/fleet/", data),
  update: (id: number, data: Partial<VehicleCreate>) => api.patch<VehicleOut>(`/fleet/${id}`, data),
  delete: (id: number) => api.delete(`/fleet/${id}`),
};

export const visibilityApi = {
  updateInstance: (path: string, visibility: string, sharedWithEmails: string[]) =>
    api.patch("/instances/visibility", { path, visibility, shared_with_emails: sharedWithEmails }),
  updateMetric: (id: number, visibility: string, sharedWithEmails: string[]) =>
    api.patch(`/metrics/${id}/visibility`, { visibility, shared_with_emails: sharedWithEmails }),
};

export const instancesApi = {
  list: (folder?: string) =>
    api.get<InstanceInfo[]>("/instances/", { params: folder ? { folder } : {} }),
  listAll: () =>
    api.get<InstanceInfo[]>("/instances/", { params: { flat: true } }),
  get: (name: string) => api.get<InstanceInfo>(`/instances/${name}`),
  delete: (path: string) =>
    api.delete("/instances/", { params: { path } }),
  content: (path: string) =>
    api.get<{ path: string; name: string; content: string }>("/instances/content", { params: { path } }),
  nodes: (name: string) =>
    api.get<{ dataset_type: string; nodes: NodeCoord[] }>("/instances/nodes", { params: { name } }),
  parseReport: (name: string) =>
    api.get<ParseReport>("/instances/parse-report", { params: { name } }),
  upload: (files: File[], visibility = "public", sharedWithEmails: string[] = []) => {
    const form = new FormData();
    files.forEach((f) => {
      const path = (f as any).webkitRelativePath || f.name;
      form.append("files", f, path);
    });
    form.append("visibility", visibility);
    form.append("shared_with_emails", JSON.stringify(sharedWithEmails));
    return api.post<{ uploaded: InstanceInfo[]; skipped: string[] }>(
      "/instances/upload",
      form,
      { headers: { "Content-Type": "multipart/form-data" } }
    );
  },
  uploadArchive: (file: File, visibility = "public", sharedWithEmails: string[] = []) => {
    const form = new FormData();
    form.append("file", file, file.name);
    form.append("visibility", visibility);
    form.append("shared_with_emails", JSON.stringify(sharedWithEmails));
    return api.post<{ uploaded: InstanceInfo[]; skipped: string[]; failed: { filename: string; error_msg: string }[] }>(
      "/instances/upload-archive",
      form,
      { headers: { "Content-Type": "multipart/form-data" } }
    );
  },
};

export const jobsApi = {
  create: (data: JobCreate) => api.post<JobOut>("/jobs/", data),
  list: () => api.get<JobOut[]>("/jobs/"),
  get: (id: number) => api.get<JobOut>(`/jobs/${id}`),
  delete: (id: number) => api.delete(`/jobs/${id}`),
  exportExcel: () => api.get("/jobs/export", { responseType: "blob" }),
};

export const solutionsApi = {
  list: () => api.get<SolutionOut[]>("/solutions/"),
  get: (id: number) => api.get<SolutionOut>(`/solutions/${id}`),
  byJob: (jobId: number) => api.get<SolutionOut>(`/solutions/by-job/${jobId}`),
  bks: (instanceName: string) => api.get<BksEntry | null>("/solutions/bks", { params: { instance_name: instanceName } }),
  stats: () => api.get<DatasetStats[]>("/solutions/stats"),
};

export const algorithmsApi = {
  list: () => api.get<AlgorithmOut[]>("/algorithms/"),
  upload: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => {
      const path = (f as any).webkitRelativePath || f.name;
      form.append("files", f, path);
    });
    return api.post<AlgorithmOut>("/algorithms/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  update: (id: number, data: { vrp_variant?: string; selected_metrics?: string; description?: string; flow_steps?: string }) =>
    api.patch<AlgorithmOut>(`/algorithms/${id}`, data),
  reanalyze: (id: number) =>
    api.post<AlgorithmOut>(`/algorithms/${id}/reanalyze`),
  delete: (id: number) => api.delete(`/algorithms/${id}`),
};

export const metricsApi = {
  list: () => api.get<MetricOut[]>("/metrics/"),
  upload: (file: File, visibility = "public", sharedWithEmails: string[] = []) => {
    const form = new FormData();
    form.append("file", file);
    form.append("visibility", visibility);
    form.append("shared_with_emails", JSON.stringify(sharedWithEmails));
    return api.post<MetricOut>("/metrics/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  delete: (id: number) => api.delete(`/metrics/${id}`),
};

export interface LLMFlowStep {
  phase: string;
  description: string;
  loop?: boolean;
  components?: { name: string; desc: string }[];
}

export interface LLMAnalysis {
  problem_variant: string;
  description: string;
  hard_constraints: string[];
  soft_constraints: string[];
  dataset_format: string;
  reference_papers: string[];
  flow_steps?: LLMFlowStep[];
}

export interface AnalyzeResponse {
  temp_id: string;
  analysis: LLMAnalysis;
  files?: string[];
  llm_available?: boolean;
}

export const uploadAnalyzeApi = {
  dataset: (files: File[], visibility = "public", sharedWithEmails: string[] = []) => {
    const form = new FormData();
    files.forEach((f) => {
      const path = (f as any).webkitRelativePath || f.name;
      form.append("files", f, path);
    });
    form.append("visibility", visibility);
    form.append("shared_with_emails", JSON.stringify(sharedWithEmails));
    return api.post<AnalyzeResponse>("/upload-analyze/dataset", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  algorithm: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => {
      const path = (f as any).webkitRelativePath || f.name;
      form.append("files", f, path);
    });
    return api.post<AnalyzeResponse>("/upload-analyze/algorithm", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  metric: (file: File, visibility = "public", sharedWithEmails: string[] = []) => {
    const form = new FormData();
    form.append("file", file);
    form.append("visibility", visibility);
    form.append("shared_with_emails", JSON.stringify(sharedWithEmails));
    return api.post<AnalyzeResponse>("/upload-analyze/metric", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  confirm: (
    tempId: string,
    kind: "dataset" | "algorithm" | "metric",
    analysis: LLMAnalysis,
    extra?: { vrp_variant?: string; selected_metrics?: string; flow_steps?: string }
  ) =>
    api.post("/upload-analyze/confirm", { temp_id: tempId, kind, analysis, ...extra }),
  reject: (kind: "dataset" | "algorithm" | "metric", tempId: string) =>
    api.delete(`/upload-analyze/reject/${kind}/${tempId}`),
};

export const ordersApi = {
  list: () => api.get<OrderOut[]>("/orders/"),
  get: (id: number) => api.get<OrderOut>(`/orders/${id}`),
  create: (data: OrderCreate) => api.post<OrderOut>("/orders/", data),
  update: (id: number, data: Partial<OrderOut>) => api.patch<OrderOut>(`/orders/${id}`, data),
  delete: (id: number) => api.delete(`/orders/${id}`),
};

// ── Types (mirrors backend schemas) ───────────────────────────────────────────

export type UserRole = "admin" | "algo_tester" | "dataset_provider" | "metric_provider";
export type JobStatus = "pending" | "running" | "done" | "failed";
export type VehicleStatus = "available" | "in_use" | "maintenance";
export type OrderStatus = "pending" | "confirmed" | "in_transit" | "delivered" | "cancelled";

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  role: UserRole;
  full_name: string;
  user_id: number;
  email: string;
}

export interface UserOut {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface UserCreate {
  email: string;
  password: string;
  full_name: string;
  role: UserRole;
}

export interface VehicleOut {
  id: number;
  plate: string;
  capacity: number;
  status: VehicleStatus;
  notes: string | null;
  created_at: string;
}

export interface VehicleCreate {
  plate: string;
  capacity: number;
  status?: VehicleStatus;
  notes?: string;
}

export interface InstanceInfo {
  name: string;
  path: string;
  num_requests?: number;
  num_vehicles?: number;
  capacity?: number;
  is_folder?: boolean;
  file_count?: number;
  uploaded_by?: string | null;
  uploaded_at?: string | null;
  uploaded_by_id?: number | null;
  visibility?: "public" | "private" | "shared" | null;
  shared_with?: number[] | null;
}

export interface JobCreate {
  instance_name: string;
  method?: string;
  time_limit_sec?: number;
  seed?: number;
}

export interface SolutionSummary {
  id: number;
  num_vehicles: number;
  total_distance: number;
  total_cost?: number | null;
  dataset_type?: string | null;
}

export interface JobOut {
  id: number;
  instance_name: string;
  status: JobStatus;
  method: string;
  time_limit_sec: number;
  seed: number;
  owner_id: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_msg: string | null;
  solution?: SolutionSummary | null;
}

export interface NodeCoord {
  id: number;
  lat: number;
  lon: number;
  type?: "depot" | "pickup" | "delivery";
  pair?: number | null;
}
export interface RouteStopOut { position: number; node_id: number; }
export interface RouteOut { route_index: number; stops: RouteStopOut[]; }
export interface SolutionOut {
  id: number;
  job_id: number;
  instance_name: string;
  method: string;
  num_vehicles: number;
  total_distance: number;
  total_cost?: number | null;
  dataset_type?: string | null;
  created_at: string;
  routes: RouteOut[];
  // Performance
  iterations?: number | null;
  elapsed_sec?: number | null;
  init_cost?: number | null;
  init_nv?: number | null;
  // Environment
  hostname?: string | null;
  os_info?: string | null;
  cpu_info?: string | null;
  ram_gb?: number | null;
  cpu_usage_pct?: number | null;
}

export interface BksEntry {
  instance_name: string;
  bks_nv: number;
  bks_cost: number;
  reference: string;
  date: string;
}

export interface DatasetStats {
  dataset: string;
  method: string;
  count: number;
  avg_nv: number;
  avg_cost: number;
  avg_init_cost: number | null;
  avg_improve_pct: number | null;
  avg_gap_nv_pct: number | null;
  avg_gap_cost_pct: number | null;
  avg_elapsed_sec: number | null;
  avg_iterations: number | null;
  avg_iter_per_sec: number | null;
}

export type ParseFieldStatus = "ok" | "derived" | "ignored" | "error";

export interface ParseField {
  category: string;
  field: string;
  status: ParseFieldStatus;
  source: string;
  value: string;
  note: string;
}

export interface ParseReport {
  instance_name: string;
  dataset_type: string;
  dataset_type_label: string;
  stats: {
    num_nodes?: number;
    num_requests?: number;
    capacity?: number;
    horizon?: number;
    depot_id?: number;
    travel_time_size?: number;
  };
  errors: string[];
  warnings: string[];
  fields: ParseField[];
}

export interface AlgorithmOut {
  id: number;
  name: string;
  description: string | null;
  is_system: boolean;
  filename: string | null;
  uploaded_by_id: number | null;
  created_at: string;
  vrp_variant: string | null;
  selected_metrics: string | null; // JSON string: ["total_distance", ...]
  flow_steps: string | null;       // JSON string: LLMFlowStep[]
}

export interface MetricOut {
  id: number;
  name: string;
  description: string | null;
  is_system: boolean;
  filename: string | null;
  uploaded_by_id: number | null;
  visibility: "public" | "private" | "shared";
  shared_with_ids: string | null;
  created_at: string;
}

export interface OrderCreate {
  description?: string;
  pickup_address: string;
  delivery_address: string;
  time_window_start?: string;
  time_window_end?: string;
}

export interface OrderOut {
  id: number;
  customer_id: number;
  description: string | null;
  status: OrderStatus;
  pickup_address: string;
  delivery_address: string;
  time_window_start: string | null;
  time_window_end: string | null;
  created_at: string;
}
