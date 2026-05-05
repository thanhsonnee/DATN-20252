import { useEffect, useRef, useState, useMemo } from "react";
import {
  CheckCircle, Upload, Trash2, Lock, FolderOpen,
  FlaskConical, GitFork, Code, RefreshCw, BarChart2, Save, Sparkles, Pencil,
} from "lucide-react";
import type { LLMFlowStep } from "@/api/client";
import toast from "react-hot-toast";
import { algorithmsApi, uploadAnalyzeApi, type AlgorithmOut, type LLMAnalysis, type AnalyzeResponse } from "@/api/client";
import { useAuth } from "@/contexts/AuthContext";
import LLMAnalysisReview from "@/components/LLMAnalysisReview";
import { useTranslation } from "react-i18next";
import { VRP_VARIANTS, VARIANT_METRICS, type MetricDef } from "@/constants/vrpVariants";

// re-export for other consumers
export { VRP_VARIANTS, VARIANT_METRICS };
export type { MetricDef };

// ── ALNS static data ──────────────────────────────────────────────────────────

type Component = { name: string; desc: string; badge?: string };

type FlowStep = {
  phaseKey: string;
  color: string;
  bgColor: string;
  borderColor: string;
  textColor: string;
  descColor: string;
  desc: string;
  loop?: boolean;
  components?: Component[];
};

const FLOW_STEPS: FlowStep[] = [
  {
    phaseKey: "algorithms.flow.init",
    color: "bg-blue-500", bgColor: "bg-blue-50", borderColor: "border-blue-100",
    textColor: "text-blue-800", descColor: "text-blue-600",
    desc: "Generate an initial solution using one of the construction methods.",
    components: [
      { name: "Greedy insertion", desc: "Insert each request at the lowest-cost position. Fast, suitable for large instances.", badge: "Recommended" },
      { name: "Regret-k insertion", desc: "Prioritize requests with high regret value — better initial solution, slower for large n." },
    ],
  },
  {
    phaseKey: "algorithms.flow.destroy",
    color: "bg-red-500", bgColor: "bg-red-50", borderColor: "border-red-100",
    textColor: "text-red-800", descColor: "text-red-600",
    desc: "Randomly select 1 of 4 destroy operators (roulette-wheel) and remove q requests from the solution.",
    components: [
      { name: "Random removal",      desc: "Randomly select requests to remove from the solution." },
      { name: "Worst removal",       desc: "Prioritize removing requests with the highest cost contribution." },
      { name: "Shaw removal",        desc: "Remove requests similar in location and time window." },
      { name: "Time-window removal", desc: "Remove requests within the same narrow time window." },
    ],
  },
  {
    phaseKey: "algorithms.flow.repair",
    color: "bg-green-500", bgColor: "bg-green-50", borderColor: "border-green-100",
    textColor: "text-green-800", descColor: "text-green-600",
    desc: "Reinsert removed requests using one of the repair operators.",
    components: [
      { name: "Greedy insertion",   desc: "Reinsert each request at the lowest-cost position." },
      { name: "Regret-2 insertion", desc: "Prioritize requests with the largest cost difference between best and second-best positions." },
    ],
  },
  {
    phaseKey: "algorithms.flow.localSearch",
    color: "bg-purple-500", bgColor: "bg-purple-50", borderColor: "border-purple-100",
    textColor: "text-purple-800", descColor: "text-purple-600",
    desc: "Improve the current solution using neighborhood search.",
    components: [
      { name: "Or-opt", desc: "Move chains of 1–3 nodes between routes to reduce total cost." },
    ],
  },
  {
    phaseKey: "algorithms.flow.accept",
    color: "bg-yellow-500", bgColor: "bg-yellow-50", borderColor: "border-yellow-100",
    textColor: "text-yellow-800", descColor: "text-yellow-600",
    desc: "Decide whether to update the current solution.",
    components: [
      { name: "Simulated Annealing", desc: "Accept a worse solution with probability e^(-Δ/T); temperature T decreases over iterations." },
    ],
  },
  {
    phaseKey: "algorithms.flow.repeat",
    color: "bg-gray-400", bgColor: "bg-gray-50", borderColor: "border-gray-200",
    textColor: "text-gray-700", descColor: "text-gray-500",
    desc: "Return to the Destroy step until the time limit is reached.",
    loop: true,
  },
];

// ── Tab types ─────────────────────────────────────────────────────────────────

type ContentTab = "overview" | "flow" | "metrics" | "code";

// ── ALNS tab content ──────────────────────────────────────────────────────────

function AlnsOverview() {
  const { t } = useTranslation();
  return (
    <div className="space-y-4">
      <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
        <p className="text-sm text-blue-900 font-medium mb-1">{t("algorithms.alnsTitle")}</p>
        <p className="text-sm text-blue-700 leading-relaxed">{t("algorithms.alnsDesc")}</p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {[
          { label: "Method",        value: "Meta-heuristic" },
          { label: "Problem Type",  value: "PDPTW" },
          { label: "Dataset",       value: "Sartori & Buriol, Li & Lim" },
          { label: "Avg. Runtime",  value: "30 – 300 seconds" },
        ].map((r) => (
          <div key={r.label} className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-500">{r.label}</p>
            <p className="text-sm font-medium text-gray-800 mt-0.5">{r.value}</p>
          </div>
        ))}
      </div>
      <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
        <p className="text-xs text-gray-500">
          {t("algorithms.detailTabHint")} <span className="font-medium text-blue-700">{t("algorithms.detailTabLink")}</span>.
        </p>
      </div>
    </div>
  );
}

function AlnsFlowAndComponents() {
  const { t } = useTranslation();
  return (
    <div className="space-y-1">
      <p className="text-xs text-gray-500 mb-3">{t("algorithms.flowIntro")}</p>

      {FLOW_STEPS.map((step, i) => (
        <div key={i} className="flex gap-3">
          {/* Left: step number + connector line */}
          <div className="flex flex-col items-center shrink-0">
            <div className={`w-7 h-7 rounded-full ${step.color} flex items-center justify-center text-white text-xs font-bold`}>
              {step.loop ? <RefreshCw size={13} /> : i + 1}
            </div>
            {i < FLOW_STEPS.length - 1 && (
              <div className="w-0.5 flex-1 bg-gray-200 my-1 min-h-[12px]" />
            )}
          </div>

          {/* Right: step info + components */}
          <div className={`flex-1 mb-3 rounded-xl border p-3 ${step.bgColor} ${step.borderColor}`}>
            <p className={`text-sm font-semibold ${step.textColor}`}>{t(step.phaseKey)}</p>
            <p className={`text-xs mt-0.5 mb-2 ${step.descColor}`}>{step.desc}</p>

            {step.components && step.components.length > 0 && (
              <div className="space-y-1.5 mt-2 pt-2 border-t border-black/5">
                {step.components.map((c) => (
                  <div key={c.name} className="flex items-start gap-2 bg-white/70 rounded-lg px-2.5 py-2">
                    <CheckCircle size={12} className={`mt-0.5 shrink-0 ${step.textColor}`} />
                    <div>
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className={`text-xs font-semibold ${step.textColor}`}>{c.name}</span>
                        {c.badge && (
                          <span className="text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded font-medium">{c.badge}</span>
                        )}
                      </div>
                      <p className={`text-[11px] mt-0.5 ${step.descColor}`}>{c.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {step.loop && (
              <p className={`text-xs italic mt-1 ${step.descColor}`}>{t("algorithms.flowLoopBack")}</p>
            )}
          </div>
        </div>
      ))}

      <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
        <p className="text-xs text-gray-500">
          <span className="font-medium text-gray-700">{t("algorithms.adaptiveMechanism")}</span>{" "}
          {t("algorithms.adaptiveDesc")}
        </p>
      </div>
    </div>
  );
}

// ── math-pdptw flow & components ─────────────────────────────────────────────

const MATH_PDPTW_STEPS = [
  {
    phase: "Khởi tạo nghiệm",
    color: "bg-blue-500", bgColor: "bg-blue-50", borderColor: "border-blue-100",
    textColor: "text-blue-800", descColor: "text-blue-600",
    desc: "Xây dựng nghiệm ban đầu bằng phương pháp tham lam hoặc tầm thường.",
    components: [
      { name: "Greedy insertion", desc: "Chèn từng yêu cầu vào vị trí có chi phí thấp nhất.", badge: "Mặc định" },
      { name: "Trivial insertion", desc: "Mỗi yêu cầu được phục vụ bởi một xe riêng (nghiệm feasible tức thì)." },
    ],
  },
  {
    phase: "AGES — Adaptive Guided Ejection Search",
    color: "bg-purple-500", bgColor: "bg-purple-50", borderColor: "border-purple-100",
    textColor: "text-purple-800", descColor: "text-purple-600",
    desc: "Tìm kiếm cục bộ hướng dẫn để giảm số lượng xe. Loại bỏ (eject) các yêu cầu khỏi tuyến đường rồi tái chèn vào các tuyến còn lại.",
    components: [
      { name: "Ejection chain", desc: "Loại bỏ yêu cầu theo chuỗi; mỗi lần eject tạo không gian cho yêu cầu tiếp theo." },
      { name: "Guided search", desc: "Sử dụng danh sách xung đột (conflict list) để hướng dẫn thứ tự ejection, tránh vòng lặp vô ích." },
      { name: "Perturbation", desc: "Khi bị kẹt, nhiễu loạn nghiệm theo xác suất để thoát khỏi cực trị cục bộ." },
    ],
  },
  {
    phase: "LNS — Large Neighborhood Search",
    color: "bg-red-500", bgColor: "bg-red-50", borderColor: "border-red-100",
    textColor: "text-red-800", descColor: "text-red-600",
    desc: "Phá hủy một phần nghiệm rồi tái xây dựng để cải thiện tổng chi phí.",
    components: [
      { name: "Shaw removal",   desc: "Loại bỏ các yêu cầu tương đồng về vị trí và cửa sổ thời gian." },
      { name: "Random removal", desc: "Loại bỏ ngẫu nhiên q yêu cầu." },
      { name: "Worst removal",  desc: "Ưu tiên loại bỏ các yêu cầu có đóng góp chi phí cao nhất." },
      { name: "Regret-k reinsertion", desc: "Tái chèn yêu cầu có giá trị regret cao nhất trước — cho nghiệm tốt hơn greedy." },
    ],
  },
  {
    phase: "Chấp nhận nghiệm (LAHC)",
    color: "bg-yellow-500", bgColor: "bg-yellow-50", borderColor: "border-yellow-100",
    textColor: "text-yellow-800", descColor: "text-yellow-600",
    desc: "Quyết định chấp nhận nghiệm mới bằng tiêu chí Late Acceptance Hill Climbing.",
    components: [
      { name: "Late Acceptance Hill Climbing", desc: "Chấp nhận nghiệm mới nếu tốt hơn nghiệm tại vị trí L bước trước trong lịch sử." },
    ],
  },
  {
    phase: "Cập nhật & Nhiễu loạn",
    color: "bg-green-500", bgColor: "bg-green-50", borderColor: "border-green-100",
    textColor: "text-green-800", descColor: "text-green-600",
    desc: "Nếu nghiệm hiện tại tốt hơn nghiệm tốt nhất → cập nhật. Ngược lại → nhiễu loạn để thoát cực trị.",
    components: [
      { name: "Sampled perturbation", desc: "Chọn ngẫu nhiên P% số yêu cầu để hoán đổi giữa các tuyến." },
    ],
  },
  {
    phase: "Lặp lại đến hết thời gian",
    color: "bg-gray-400", bgColor: "bg-gray-50", borderColor: "border-gray-200",
    textColor: "text-gray-700", descColor: "text-gray-500",
    desc: "Quay lại bước AGES cho đến khi đạt giới hạn thời gian.",
    loop: true,
  },
];

function MathPdptwFlow() {
  return (
    <div className="space-y-1">
      <p className="text-xs text-gray-500 mb-3">
        Luồng thực thi của thuật toán AGES+LNS (Sartori &amp; Buriol, 2021).
      </p>
      {MATH_PDPTW_STEPS.map((step, i) => (
        <div key={i} className="flex gap-3">
          <div className="flex flex-col items-center shrink-0">
            <div className={`w-7 h-7 rounded-full ${step.color} flex items-center justify-center text-white text-xs font-bold`}>
              {step.loop ? <RefreshCw size={13} /> : i + 1}
            </div>
            {i < MATH_PDPTW_STEPS.length - 1 && (
              <div className="w-0.5 flex-1 bg-gray-200 my-1 min-h-[12px]" />
            )}
          </div>
          <div className={`flex-1 mb-3 rounded-xl border p-3 ${step.bgColor} ${step.borderColor}`}>
            <p className={`text-sm font-semibold ${step.textColor}`}>{step.phase}</p>
            <p className={`text-xs mt-0.5 mb-2 ${step.descColor}`}>{step.desc}</p>
            {step.components && step.components.length > 0 && (
              <div className="space-y-1.5 mt-2 pt-2 border-t border-black/5">
                {step.components.map((c) => (
                  <div key={c.name} className="flex items-start gap-2 bg-white/70 rounded-lg px-2.5 py-2">
                    <CheckCircle size={12} className={`mt-0.5 shrink-0 ${step.textColor}`} />
                    <div>
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className={`text-xs font-semibold ${step.textColor}`}>{c.name}</span>
                        {"badge" in c && c.badge && (
                          <span className="text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded font-medium">{c.badge}</span>
                        )}
                      </div>
                      <p className={`text-[11px] mt-0.5 ${step.descColor}`}>{c.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {step.loop && (
              <p className={`text-xs italic mt-1 ${step.descColor}`}>Lặp lại cho đến khi hết thời gian.</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Dynamic flow renderer (from DB / LLM analysis) ───────────────────────────

const STEP_COLORS = [
  { color: "bg-blue-500",   bgColor: "bg-blue-50",   borderColor: "border-blue-100",   textColor: "text-blue-800",   descColor: "text-blue-600" },
  { color: "bg-red-500",    bgColor: "bg-red-50",    borderColor: "border-red-100",    textColor: "text-red-800",    descColor: "text-red-600" },
  { color: "bg-green-500",  bgColor: "bg-green-50",  borderColor: "border-green-100",  textColor: "text-green-800",  descColor: "text-green-600" },
  { color: "bg-purple-500", bgColor: "bg-purple-50", borderColor: "border-purple-100", textColor: "text-purple-800", descColor: "text-purple-600" },
  { color: "bg-yellow-500", bgColor: "bg-yellow-50", borderColor: "border-yellow-100", textColor: "text-yellow-800", descColor: "text-yellow-600" },
  { color: "bg-orange-500", bgColor: "bg-orange-50", borderColor: "border-orange-100", textColor: "text-orange-800", descColor: "text-orange-600" },
];

function DynamicFlow({ algo, onReanalyzed }: { algo: AlgorithmOut; onReanalyzed: (updated: AlgorithmOut) => void }) {
  const [reanalyzing, setReanalyzing] = useState(false);

  const steps: LLMFlowStep[] = useMemo(() => {
    try { return algo.flow_steps ? JSON.parse(algo.flow_steps) : []; }
    catch { return []; }
  }, [algo.flow_steps]);

  const handleReanalyze = async () => {
    setReanalyzing(true);
    try {
      const res = await algorithmsApi.reanalyze(algo.id);
      onReanalyzed(res.data);
      toast.success("Đã phân tích lại luồng thuật toán");
    } catch {
      toast.error("Phân tích thất bại");
    } finally {
      setReanalyzing(false);
    }
  };

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs text-gray-500">Luồng thực thi được phân tích bởi AI.</p>
        <button
          onClick={handleReanalyze}
          disabled={reanalyzing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          <Sparkles size={12} className={reanalyzing ? "animate-spin" : ""} />
          {reanalyzing ? "Đang phân tích..." : "Phân tích lại"}
        </button>
      </div>

      {steps.length === 0 ? (
        <div className="text-center py-6 text-gray-400 text-sm">
          Chưa có thông tin luồng. Nhấn "Phân tích lại" để AI tạo luồng từ mã nguồn.
        </div>
      ) : (
        steps.map((step, i) => {
          const c = STEP_COLORS[i % STEP_COLORS.length];
          return (
            <div key={i} className="flex gap-3">
              <div className="flex flex-col items-center shrink-0">
                <div className={`w-7 h-7 rounded-full ${c.color} flex items-center justify-center text-white text-xs font-bold`}>
                  {step.loop ? <RefreshCw size={13} /> : i + 1}
                </div>
                {i < steps.length - 1 && <div className="w-0.5 flex-1 bg-gray-200 my-1 min-h-[12px]" />}
              </div>
              <div className={`flex-1 mb-3 rounded-xl border p-3 ${c.bgColor} ${c.borderColor}`}>
                <p className={`text-sm font-semibold ${c.textColor}`}>{step.phase}</p>
                <p className={`text-xs mt-0.5 mb-2 ${c.descColor}`}>{step.description}</p>
                {step.components && step.components.length > 0 && (
                  <div className="space-y-1.5 mt-2 pt-2 border-t border-black/5">
                    {step.components.map((comp, j) => (
                      <div key={j} className="flex items-start gap-2 bg-white/70 rounded-lg px-2.5 py-2">
                        <CheckCircle size={12} className={`mt-0.5 shrink-0 ${c.textColor}`} />
                        <div>
                          <span className={`text-xs font-semibold ${c.textColor}`}>{comp.name}</span>
                          <p className={`text-[11px] mt-0.5 ${c.descColor}`}>{comp.desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {step.loop && (
                  <p className={`text-xs italic mt-1 ${c.descColor}`}>Lặp lại cho đến khi hết thời gian.</p>
                )}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

// ── System plugin overview (non-ALNS system algorithms) ──────────────────────

function SystemPluginOverview({
  algo, onUpdate,
}: {
  algo: AlgorithmOut;
  onUpdate: (updated: AlgorithmOut) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [desc, setDesc] = useState(algo.description ?? "");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await algorithmsApi.update(algo.id, { description: desc });
      onUpdate(res.data);
      setEditing(false);
      toast.success("Đã lưu mô tả");
    } catch { toast.error("Lưu thất bại"); }
    finally { setSaving(false); }
  };

  const infoRows = [
    { label: "Problem Type", value: algo.vrp_variant ?? "—" },
    { label: "Tạo lúc",     value: new Date(algo.created_at).toLocaleDateString() },
  ];

  return (
    <div className="space-y-4">
      <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
        <div className="flex items-start justify-between gap-2 mb-1">
          <p className="text-sm text-blue-900 font-medium">{algo.name}</p>
          <button onClick={() => setEditing(!editing)} className="text-blue-400 hover:text-blue-600 shrink-0">
            <Pencil size={13} />
          </button>
        </div>
        {editing ? (
          <div className="space-y-2">
            <textarea
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              rows={4}
              className="w-full text-sm border border-blue-200 rounded-lg p-2 bg-white focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setEditing(false)} className="px-3 py-1 text-xs border border-gray-300 rounded-lg hover:bg-gray-50">Hủy</button>
              <button onClick={handleSave} disabled={saving} className="px-3 py-1 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                {saving ? "Đang lưu..." : "Lưu"}
              </button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-blue-700 leading-relaxed">{algo.description ?? "Không có mô tả."}</p>
        )}
      </div>
      <div className="grid grid-cols-2 gap-3">
        {infoRows.map((r) => (
          <div key={r.label} className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-500">{r.label}</p>
            <p className="text-sm font-medium text-gray-800 mt-0.5">{r.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Custom algorithm tab content ──────────────────────────────────────────────

function CustomOverview({ algo, onUpdate }: { algo: AlgorithmOut; onUpdate: (updated: AlgorithmOut) => void }) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [desc, setDesc] = useState(algo.description ?? "");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await algorithmsApi.update(algo.id, { description: desc });
      onUpdate(res.data);
      setEditing(false);
      toast.success(t("algorithms.metricsSaveSuccess"));
    } catch { toast.error(t("algorithms.metricsSaveFail")); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-4">
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
        <div className="flex items-start justify-between gap-2 mb-1">
          <p className="text-sm font-medium text-gray-800">{algo.name}</p>
          <button onClick={() => setEditing(!editing)} className="text-gray-400 hover:text-gray-600 shrink-0">
            <Pencil size={13} />
          </button>
        </div>
        {editing ? (
          <div className="space-y-2">
            <textarea
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              rows={4}
              className="w-full text-sm border border-gray-300 rounded-lg p-2 bg-white focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setEditing(false)} className="px-3 py-1 text-xs border border-gray-300 rounded-lg hover:bg-gray-50">Hủy</button>
              <button onClick={handleSave} disabled={saving} className="px-3 py-1 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                {saving ? "Đang lưu..." : "Lưu"}
              </button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-500">{algo.description ?? t("algorithms.customNoDesc")}</p>
        )}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs text-gray-500">{t("algorithms.customType")}</p>
          <p className="text-sm font-medium text-gray-800 mt-0.5">{t("algorithms.customTypeValue")}</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs text-gray-500">{t("algorithms.customEntryPoint")}</p>
          <p className="text-sm font-mono text-gray-800 mt-0.5 truncate">{algo.filename ?? "—"}</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs text-gray-500">{t("algorithms.customCreatedAt")}</p>
          <p className="text-sm font-medium text-gray-800 mt-0.5">
            {new Date(algo.created_at).toLocaleDateString()}
          </p>
        </div>
      </div>
    </div>
  );
}

function CustomCode({ algo }: { algo: AlgorithmOut }) {
  const { t } = useTranslation();
  const [code, setCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!algo.filename) { setLoading(false); return; }
    setCode(null);
    setLoading(false);
  }, [algo.id]);

  return (
    <div>
      <p className="text-xs text-gray-500 mb-2">
        {t("algorithms.codeFileLabel")} <span className="font-mono text-gray-700">{algo.filename ?? "—"}</span>
      </p>
      {loading ? (
        <p className="text-xs text-gray-400">{t("common.loading")}</p>
      ) : (
        <div className="bg-gray-900 rounded-lg p-4 text-xs font-mono text-gray-300 overflow-x-auto">
          {code ?? (
            <span className="text-gray-500 italic">
              {t("algorithms.codeLoadError")}<br/>
              {t("algorithms.codeViewPath")}{algo.filename}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ── Metrics tab ───────────────────────────────────────────────────────────────

function MetricsTab({ algo, onSaved }: { algo: AlgorithmOut; onSaved: (updated: AlgorithmOut) => void }) {
  const { t } = useTranslation();
  const isAlns = algo.is_system && algo.name === "ALNS";
  const defaultVariant = algo.vrp_variant ?? (isAlns ? "PDPTW" : "");
  const defaultMetrics: string[] = (() => {
    try { return algo.selected_metrics ? JSON.parse(algo.selected_metrics) : []; }
    catch { return []; }
  })();

  const [variant, setVariant] = useState(defaultVariant);
  const [selected, setSelected] = useState<string[]>(
    defaultMetrics.length > 0
      ? defaultMetrics
      : VARIANT_METRICS[defaultVariant]?.map((m) => m.key) ?? []
  );
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const availableMetrics = VARIANT_METRICS[variant] ?? [];

  const handleVariantChange = (v: string) => {
    setVariant(v);
    setSelected(VARIANT_METRICS[v]?.map((m) => m.key) ?? []);
    setDirty(true);
  };

  const toggleMetric = (key: string) => {
    setSelected((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
    setDirty(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await algorithmsApi.update(algo.id, {
        vrp_variant: variant || undefined,
        selected_metrics: JSON.stringify(selected),
      });
      onSaved(res.data);
      setDirty(false);
      toast.success(t("algorithms.metricsSaveSuccess"));
    } catch {
      toast.error(t("algorithms.metricsSaveFail"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Step 1: pick variant */}
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
          {t("algorithms.metricsStep1")}
        </p>
        <div className="grid grid-cols-2 gap-2">
          {VRP_VARIANTS.map((v) => {
            const active = variant === v.key;
            return (
              <button
                key={v.key}
                onClick={() => handleVariantChange(v.key)}
                disabled={isAlns}
                className={`text-left px-3 py-2.5 rounded-lg border text-sm transition-colors
                  ${active
                    ? "border-blue-500 bg-blue-50 text-blue-800"
                    : "border-gray-200 hover:border-gray-300 text-gray-700"}
                  ${isAlns ? "cursor-default opacity-80" : "cursor-pointer"}`}
              >
                <span className="font-semibold">{v.label}</span>
                <span className="block text-xs text-gray-500 mt-0.5">{v.desc}</span>
              </button>
            );
          })}
        </div>
        {isAlns && (
          <p className="text-xs text-gray-400 mt-1.5">{t("algorithms.metricsSystemNote")}</p>
        )}
      </div>

      {/* Step 2: select metrics */}
      {variant && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            {t("algorithms.metricsStep2")}
          </p>
          {availableMetrics.length === 0 ? (
            <p className="text-xs text-gray-400">{t("algorithms.metricsNoMetrics")}</p>
          ) : (
            <div className="space-y-2">
              {availableMetrics.map((m) => {
                const checked = selected.includes(m.key);
                return (
                  <label
                    key={m.key}
                    className={`flex items-start gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors
                      ${checked ? "border-blue-200 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleMetric(m.key)}
                      className="mt-0.5 accent-blue-600 shrink-0"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium text-gray-800">{m.label}</span>
                        {m.unit && (
                          <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">{m.unit}</span>
                        )}
                        <span className={`text-xs px-1.5 py-0.5 rounded font-medium
                          ${m.better === "lower" ? "bg-green-50 text-green-700" : "bg-purple-50 text-purple-700"}`}>
                          {m.better === "lower"
                            ? t("algorithms.metricsBetter_lower")
                            : t("algorithms.metricsBetter_higher")}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5">{m.desc}</p>
                    </div>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Save button */}
      {variant && (
        <div className="flex items-center justify-between pt-1">
          <p className="text-xs text-gray-400">
            {t("algorithms.metricsSelected", { count: selected.length, total: availableMetrics.length })}
          </p>
          <button
            onClick={handleSave}
            disabled={saving || !dirty}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-40"
          >
            <Save size={14} /> {saving ? t("btn.savingConfig") : t("btn.saveConfig")}
          </button>
        </div>
      )}
    </div>
  );
}

// ── Algorithm detail panel ────────────────────────────────────────────────────

function AlgorithmDetail({
  algo,
  isSystem,
  onDelete,
  canDelete,
  onAlgoUpdate,
}: {
  algo: AlgorithmOut;
  isSystem: boolean;
  onDelete?: () => void;
  canDelete: boolean;
  onAlgoUpdate: (updated: AlgorithmOut) => void;
}) {
  const { t } = useTranslation();
  const isAlns = isSystem && algo.name === "ALNS";

  const ALNS_TABS: { key: ContentTab; label: string; icon: React.ReactNode }[] = [
    { key: "overview", label: t("algorithms.tabOverview"), icon: <FlaskConical size={14} /> },
    { key: "flow",     label: t("algorithms.tabFlow"),     icon: <GitFork size={14} /> },
    { key: "metrics",  label: t("algorithms.tabMetrics"),  icon: <BarChart2 size={14} /> },
  ];

  const SYSTEM_PLUGIN_TABS: { key: ContentTab; label: string; icon: React.ReactNode }[] = [
    { key: "overview", label: t("algorithms.tabOverview"), icon: <FlaskConical size={14} /> },
    { key: "flow",     label: t("algorithms.tabFlow"),     icon: <GitFork size={14} /> },
    { key: "metrics",  label: t("algorithms.tabMetrics"),  icon: <BarChart2 size={14} /> },
  ];

  const CUSTOM_TABS: { key: ContentTab; label: string; icon: React.ReactNode }[] = [
    { key: "overview", label: t("algorithms.tabOverview"), icon: <FlaskConical size={14} /> },
    { key: "flow",     label: t("algorithms.tabFlow"),     icon: <GitFork size={14} /> },
    { key: "metrics",  label: t("algorithms.tabMetrics"),  icon: <BarChart2 size={14} /> },
    { key: "code",     label: t("algorithms.tabCode"),     icon: <Code size={14} /> },
  ];

  const tabs = isAlns ? ALNS_TABS : isSystem ? SYSTEM_PLUGIN_TABS : CUSTOM_TABS;
  const [activeTab, setActiveTab] = useState<ContentTab>(tabs[0].key);

  // dataset tags shown below algorithm name in header
  const VARIANT_TAGS: Record<string, { label: string; color: string }[]> = {
    "PDPTW": [
      { label: "Sartori & Buriol", color: "bg-blue-100 text-blue-700" },
      { label: "Li & Lim",         color: "bg-purple-100 text-purple-700" },
      { label: "Ropke-Cordeau",    color: "bg-indigo-100 text-indigo-700" },
    ],
    "2E-VRP": [
      { label: "2E-EVRP",       color: "bg-teal-100 text-teal-700" },
      { label: "2E-VRP-PDD",    color: "bg-cyan-100 text-cyan-700" },
    ],
  };
  const datasetTags = isAlns
    ? [
        { label: "Sartori & Buriol", color: "bg-blue-100 text-blue-700" },
        { label: "Li & Lim",         color: "bg-purple-100 text-purple-700" },
      ]
    : (VARIANT_TAGS[algo.vrp_variant ?? ""] ?? []);

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
      {/* Detail header */}
      <div className="flex items-start justify-between px-5 py-4 border-b">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-base font-bold text-gray-900">{algo.name}</h2>
            {isSystem ? (
              <>
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-green-100 text-green-700">{t("algorithms.tagActive")}</span>
                <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
                  <Lock size={10} /> {t("algorithms.tagSystem")}
                </span>
              </>
            ) : (
              <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">{t("algorithms.tagCustom")}</span>
            )}
          </div>
          {datasetTags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {datasetTags.map((tag) => (
                <span key={tag.label} className={`text-xs px-2 py-0.5 rounded-full font-medium ${tag.color}`}>
                  {tag.label}
                </span>
              ))}
            </div>
          )}
        </div>
        {!isSystem && canDelete && (
          <button onClick={onDelete} className="p-1.5 text-gray-300 hover:text-red-500 rounded-lg hover:bg-red-50 shrink-0 ml-4">
            <Trash2 size={15} />
          </button>
        )}
      </div>

      {/* Content tabs */}
      <div className="flex gap-0 border-b px-5">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium border-b-2 transition-colors -mb-px
              ${activeTab === tab.key
                ? "border-blue-500 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"}`}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="px-5 py-4">
        {isAlns ? (
          <>
            {activeTab === "overview" && <AlnsOverview />}
            {activeTab === "flow"     && <AlnsFlowAndComponents />}
            {activeTab === "metrics"  && <MetricsTab algo={algo} onSaved={onAlgoUpdate} />}
          </>
        ) : isSystem ? (
          <>
            {activeTab === "overview" && <SystemPluginOverview algo={algo} onUpdate={onAlgoUpdate} />}
            {activeTab === "flow"     && <DynamicFlow algo={algo} onReanalyzed={onAlgoUpdate} />}
            {activeTab === "metrics"  && <MetricsTab algo={algo} onSaved={onAlgoUpdate} />}
          </>
        ) : (
          <>
            {activeTab === "overview" && <CustomOverview algo={algo} onUpdate={onAlgoUpdate} />}
            {activeTab === "flow"     && <DynamicFlow algo={algo} onReanalyzed={onAlgoUpdate} />}
            {activeTab === "metrics"  && <MetricsTab algo={algo} onSaved={onAlgoUpdate} />}
            {activeTab === "code"     && <CustomCode algo={algo} />}
          </>
        )}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AlgorithmsPage() {
  const { t } = useTranslation();
  const { isAlgoTester, isAdmin } = useAuth();
  const [algorithms, setAlgorithms] = useState<AlgorithmOut[]>([]);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [selectedAlgoId, setSelectedAlgoId] = useState<number | null>(null);
  const [llmResult, setLlmResult] = useState<AnalyzeResponse | null>(null);
  const [llmAnalysis, setLlmAnalysis] = useState<LLMAnalysis | null>(null);
  const [pendingMetrics, setPendingMetrics] = useState<string[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const folderRef = useRef<HTMLInputElement>(null);

  const load = () =>
    algorithmsApi.list().then((r) => {
      setAlgorithms(r.data);
      setSelectedAlgoId((prev) => prev ?? r.data[0]?.id ?? null);
    }).catch(() => {});

  useEffect(() => { load(); }, []);

  const _buildPluginTemplate = (files: File[]): string => {
    const rel0 = (files[0] as any).webkitRelativePath || files[0].name;
    const folderName = rel0.split("/")[0] || "algorithm";
    const pyFiles = files.filter((f) => ((f as any).webkitRelativePath || f.name).endsWith(".py"));
    if (pyFiles.length > 0) {
      const firstRel = ((pyFiles[0] as any).webkitRelativePath || pyFiles[0].name)
        .split("/").slice(1).join("/") || pyFiles[0].name;
      return `from pathlib import Path\nimport sys\nsys.path.insert(0, str(Path(__file__).parent))\n\n# from ${firstRel.replace(".py", "")} import ...\n\ndef get_name() -> str:\n    return "${folderName}"\n\ndef get_description() -> str:\n    return "Algorithm ${folderName}"\n\ndef run(instance, time_limit_sec: float, seed: int, **kwargs):\n    raise NotImplementedError("Implement run() here")\n`;
    }
    return `import subprocess\nfrom pathlib import Path\n\ndef get_name() -> str:\n    return "${folderName}"\n\ndef get_description() -> str:\n    return "Algorithm ${folderName}"\n\ndef run(instance, time_limit_sec: float, seed: int, **kwargs):\n    here = Path(__file__).parent\n    raise NotImplementedError("Implement run() to call binary in this folder")\n`;
  };

  const _analyzeFiles = async (files: File[]) => {
    setAnalyzing(true);
    try {
      const folderName = ((files[0] as any).webkitRelativePath || files[0].name).split("/")[0] || "algorithm";
      const pluginCode = _buildPluginTemplate(files);
      const pluginBlob = new Blob([pluginCode], { type: "text/x-python" });
      const pluginFile = new File([pluginBlob], `${folderName}/plugin.py`);
      const withPlugin = [...files.filter((f) => {
        const rel = ((f as any).webkitRelativePath || f.name);
        return !rel.endsWith("plugin.py");
      }), pluginFile];

      const res = await uploadAnalyzeApi.algorithm(withPlugin);
      setLlmResult(res.data);
      setLlmAnalysis(res.data.analysis);
      const defaultMetrics = VARIANT_METRICS[res.data.analysis.problem_variant]?.map((m) => m.key) ?? [];
      setPendingMetrics(defaultMetrics);
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? t("algorithms.uploadFailed"));
    } finally {
      setAnalyzing(false);
      if (fileRef.current) fileRef.current.value = "";
      if (folderRef.current) folderRef.current.value = "";
    }
  };

  const handleLLMConfirm = async () => {
    if (!llmResult || !llmAnalysis) return;
    setUploading(true);
    try {
      await uploadAnalyzeApi.confirm(llmResult.temp_id, "algorithm", llmAnalysis, {
        vrp_variant: llmAnalysis.problem_variant || undefined,
        selected_metrics: JSON.stringify(pendingMetrics),
        flow_steps: llmAnalysis.flow_steps ? JSON.stringify(llmAnalysis.flow_steps) : undefined,
      });
      toast.success(t("algorithms.uploadSuccess"));
      load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? t("algorithms.uploadFailed"));
    } finally {
      setUploading(false);
      setLlmResult(null);
      setLlmAnalysis(null);
      setPendingMetrics([]);
    }
  };

  const handleLLMReject = async () => {
    if (!llmResult) return;
    try { await uploadAnalyzeApi.reject("algorithm", llmResult.temp_id); } catch {}
    setLlmResult(null);
    setLlmAnalysis(null);
    setPendingMetrics([]);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    _analyzeFiles(files);
  };

  const handleFolderSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    _analyzeFiles(files);
  };

  const handleDelete = async (id: number) => {
    try {
      await algorithmsApi.delete(id);
      toast.success(t("algorithms.deleteSuccess"));
      if (selectedAlgoId === id) setSelectedAlgoId(null);
      load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? t("algorithms.deleteFailed"));
    } finally {
      setDeleteId(null);
    }
  };

  const systemAlgos = algorithms.filter((a) => a.is_system);
  const userAlgos = algorithms.filter((a) => !a.is_system);
  const selectedAlgo = algorithms.find((a) => a.id === selectedAlgoId) ?? null;

  return (
    <div>
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t("algorithms.title")}</h1>
          <p className="text-sm text-gray-500 mt-0.5">{t("algorithms.subtitle")}</p>
        </div>
        {isAlgoTester && (
          <div className="flex gap-2">
            <input ref={fileRef} type="file" accept=".py" className="hidden" onChange={handleFileUpload} />
            {isAdmin && (
              <input ref={folderRef} type="file"
                // @ts-expect-error webkitdirectory
                webkitdirectory="" multiple
                className="hidden" onChange={handleFolderSelect} />
            )}
            <button onClick={() => fileRef.current?.click()} disabled={uploading}
              className="inline-flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50">
              <Upload size={16} /> {t("btn.uploadFilePy")}
            </button>
            {isAdmin && (
              <button onClick={() => folderRef.current?.click()} disabled={uploading}
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50">
                <FolderOpen size={16} /> {uploading ? t("btn.uploadingFolder") : t("btn.uploadFolderBtn")}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        {[
          { label: t("algorithms.cardSystem"),    value: systemAlgos.length },
          { label: t("algorithms.cardCustom"),    value: userAlgos.length },
          { label: t("algorithms.cardInitMethods"), value: 2 },
          { label: t("algorithms.cardDestroyOps"), value: 4 },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 text-center">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className="text-2xl font-bold text-gray-800 mt-0.5">{s.value}</p>
          </div>
        ))}
      </div>

      {/* Algorithm selector tabs */}
      {algorithms.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm mb-4">
          <div className="flex items-center gap-1 px-4 py-3 overflow-x-auto">
            {[...systemAlgos, ...userAlgos].map((algo) => {
              const isSelected = selectedAlgoId === algo.id;
              return (
                <button
                  key={algo.id}
                  onClick={() => setSelectedAlgoId(algo.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors
                    ${isSelected
                      ? "bg-blue-600 text-white shadow-sm"
                      : "text-gray-600 hover:bg-gray-100"}`}
                >
                  {algo.name}
                  {algo.is_system ? (
                    <span className={`text-xs px-1.5 py-0.5 rounded-full ${isSelected ? "bg-blue-500 text-blue-100" : "bg-green-100 text-green-700"}`}>
                      {t("algorithms.tagSystem")}
                    </span>
                  ) : (
                    <span className={`text-xs px-1.5 py-0.5 rounded-full ${isSelected ? "bg-blue-500 text-blue-100" : "bg-gray-100 text-gray-500"}`}>
                      {t("algorithms.tagCustom")}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Selected algorithm detail */}
      {selectedAlgo && (
        <AlgorithmDetail
          key={selectedAlgo.id}
          algo={selectedAlgo}
          isSystem={selectedAlgo.is_system}
          canDelete={isAlgoTester && !selectedAlgo.is_system}
          onDelete={() => setDeleteId(selectedAlgo.id)}
          onAlgoUpdate={(updated) =>
            setAlgorithms((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
          }
        />
      )}

      {/* Analyzing overlay */}
      {analyzing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl px-8 py-6 flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-gray-600">AI đang phân tích mã nguồn...</p>
          </div>
        </div>
      )}

      {/* LLM analysis review modal */}
      {llmResult && llmAnalysis && (() => {
        const availableMetrics = VARIANT_METRICS[llmAnalysis.problem_variant] ?? [];
        const toggleMetric = (key: string) =>
          setPendingMetrics((prev) => prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]);
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-xl mx-4 flex flex-col max-h-[90vh]">
              <div className="px-5 py-4 border-b">
                <h3 className="font-semibold text-gray-900">Xác nhận phân tích thuật toán</h3>
                <p className="text-xs text-gray-500 mt-0.5">Kiểm tra và chỉnh sửa kết quả AI trước khi lưu</p>
              </div>
              <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
                <LLMAnalysisReview
                  analysis={llmAnalysis}
                  onChange={(updated) => {
                    setLlmAnalysis(updated);
                    if (updated.problem_variant !== llmAnalysis.problem_variant) {
                      setPendingMetrics(VARIANT_METRICS[updated.problem_variant]?.map((m) => m.key) ?? []);
                    }
                  }}
                  llmAvailable={llmResult.llm_available}
                  kind="algorithm"
                />
                {availableMetrics.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Độ đo đánh giá</p>
                    <div className="space-y-1.5">
                      {availableMetrics.map((m) => {
                        const checked = pendingMetrics.includes(m.key);
                        return (
                          <label key={m.key}
                            className={`flex items-start gap-3 px-3 py-2 rounded-lg border cursor-pointer transition-colors
                              ${checked ? "border-blue-200 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}>
                            <input type="checkbox" checked={checked} onChange={() => toggleMetric(m.key)}
                              className="mt-0.5 accent-blue-600 shrink-0" />
                            <div>
                              <span className="text-sm font-medium text-gray-800">{m.label}</span>
                              {m.unit && <span className="ml-1.5 text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">{m.unit}</span>}
                              <p className="text-xs text-gray-500 mt-0.5">{m.desc}</p>
                            </div>
                          </label>
                        );
                      })}
                    </div>
                    <p className="text-xs text-gray-400 mt-1.5">{pendingMetrics.length}/{availableMetrics.length} độ đo được chọn</p>
                  </div>
                )}
              </div>
              <div className="flex justify-between gap-3 px-5 py-4 border-t">
                <button onClick={handleLLMReject} disabled={uploading}
                  className="px-4 py-2 text-sm rounded-lg border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50">
                  Hủy upload
                </button>
                <button onClick={handleLLMConfirm} disabled={uploading}
                  className="px-5 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 font-medium">
                  {uploading ? "Đang lưu..." : "Xác nhận & Lưu"}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Confirm delete */}
      {deleteId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="font-semibold text-gray-900 mb-2">{t("algorithms.deleteTitle")}</h3>
            <p className="text-sm text-gray-600 mb-4">{t("algorithms.deleteMsg")}</p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setDeleteId(null)}
                className="px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50">{t("btn.cancel")}</button>
              <button onClick={() => handleDelete(deleteId)}
                className="px-4 py-2 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700">{t("btn.delete")}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
