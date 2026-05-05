/**
 * Reusable panel for reviewing and editing LLM analysis results.
 * Used inside upload modals for dataset / algorithm / metric.
 */
import { useState } from "react";
import { Plus, X, Sparkles, Database } from "lucide-react";
import type { LLMAnalysis } from "@/api/client";
import { VRP_VARIANTS, VARIANT_DATASET_LABELS, DATASET_FORMAT_OPTIONS } from "@/constants/vrpVariants";

interface Props {
  analysis: LLMAnalysis;
  onChange: (updated: LLMAnalysis) => void;
  llmAvailable?: boolean;
  kind?: "dataset" | "algorithm" | "metric";
}

function TagList({
  items,
  onChange,
  placeholder,
}: {
  items: string[];
  onChange: (items: string[]) => void;
  placeholder: string;
}) {
  const [input, setInput] = useState("");

  const add = () => {
    const v = input.trim();
    if (v && !items.includes(v)) onChange([...items, v]);
    setInput("");
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {items.map((item, i) => (
          <span key={i}
            className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 border border-blue-200 rounded text-xs text-blue-800">
            {item}
            <button onClick={() => onChange(items.filter((_, j) => j !== i))}
              className="text-blue-400 hover:text-blue-700">
              <X size={10} />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())}
          placeholder={placeholder}
          className="flex-1 px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-400"
        />
        <button onClick={add}
          className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-lg border border-blue-200">
          <Plus size={13} />
        </button>
      </div>
    </div>
  );
}

export default function LLMAnalysisReview({ analysis, onChange, llmAvailable = true, kind }: Props) {
  const set = <K extends keyof LLMAnalysis>(key: K, val: LLMAnalysis[K]) =>
    onChange({ ...analysis, [key]: val });

  const suggestedDatasets = VARIANT_DATASET_LABELS[analysis.problem_variant] ?? [];
  const variantMatched = VRP_VARIANTS.some((v) => v.key === analysis.problem_variant);

  return (
    <div className="space-y-4 text-sm">
      {llmAvailable ? (
        <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-800">
          <Sparkles size={13} className="shrink-0 mt-0.5 text-amber-500" />
          AI đã phân tích nội dung upload. Kiểm tra và chỉnh sửa nếu cần trước khi xác nhận.
        </div>
      ) : (
        <div className="bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 text-xs text-gray-600">
          ⚠️ AI API chưa khả dụng. Vui lòng <strong>điền thủ công</strong> các thông tin bên dưới trước khi xác nhận.
        </div>
      )}

      {/* Problem variant — picker for algorithm/metric, free text for dataset */}
      <div>
        <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">
          Biến thể bài toán
        </label>
        <div className="grid grid-cols-2 gap-1.5 mb-2">
          {VRP_VARIANTS.map((v) => {
            const active = analysis.problem_variant === v.key;
            return (
              <button
                key={v.key}
                type="button"
                onClick={() => set("problem_variant", v.key)}
                className={`text-left px-3 py-2 rounded-lg border text-xs transition-colors
                  ${active
                    ? "border-blue-500 bg-blue-50 text-blue-800"
                    : "border-gray-200 hover:border-gray-300 text-gray-700"}`}
              >
                <span className="font-semibold">{v.label}</span>
                <span className="block text-gray-500 mt-0.5">{v.desc}</span>
              </button>
            );
          })}
        </div>
        {/* Show custom value if LLM returned something not in our list */}
        {!variantMatched && analysis.problem_variant && analysis.problem_variant !== "Unknown" && (
          <p className="text-xs text-amber-600 mt-1">
            AI nhận diện: <strong>{analysis.problem_variant}</strong> — chọn biến thể gần nhất ở trên.
          </p>
        )}
        {(!analysis.problem_variant || analysis.problem_variant === "Unknown") && (
          <p className="text-xs text-red-500 mt-1">AI không nhận diện được biến thể — vui lòng chọn thủ công.</p>
        )}
      </div>

      {/* Suggested test datasets (only for algorithm) */}
      {kind === "algorithm" && suggestedDatasets.length > 0 && (
        <div className="flex items-start gap-2 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2.5">
          <Database size={13} className="shrink-0 mt-0.5 text-blue-500" />
          <div className="text-xs text-blue-800">
            <span className="font-semibold">Dataset phù hợp để chạy thử:</span>{" "}
            {suggestedDatasets.join(", ")}
            <span className="block text-blue-600 mt-0.5">Hệ thống sẽ tự động chạy kiểm tra trên 1 instance nhỏ nhất.</span>
          </div>
        </div>
      )}

      {/* Description */}
      <div>
        <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">
          Mô tả
        </label>
        <textarea
          value={analysis.description}
          onChange={(e) => set("description", e.target.value)}
          rows={3}
          className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-400 resize-none"
        />
      </div>

      {/* Hard constraints */}
      <div>
        <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">
          Ràng buộc cứng
        </label>
        <TagList
          items={analysis.hard_constraints}
          onChange={(v) => set("hard_constraints", v)}
          placeholder="Thêm ràng buộc cứng..."
        />
      </div>

      {/* Soft constraints */}
      <div>
        <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">
          Ràng buộc mềm / Mục tiêu
        </label>
        <TagList
          items={analysis.soft_constraints}
          onChange={(v) => set("soft_constraints", v)}
          placeholder="Thêm mục tiêu..."
        />
      </div>

      {/* Dataset format — dropdown for dataset kind, hidden for algorithm/metric */}
      {kind !== "algorithm" && (
        <div>
          <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">
            Định dạng dataset
          </label>
          {kind === "dataset" ? (
            <select
              value={analysis.dataset_format}
              onChange={(e) => set("dataset_format", e.target.value)}
              className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-400 bg-white"
            >
              {DATASET_FORMAT_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          ) : (
            <input
              value={analysis.dataset_format}
              onChange={(e) => set("dataset_format", e.target.value)}
              className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          )}
        </div>
      )}

      {/* Reference papers */}
      <div>
        <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">
          Bài báo tham chiếu
        </label>
        <TagList
          items={analysis.reference_papers}
          onChange={(v) => set("reference_papers", v)}
          placeholder="Thêm tên bài báo..."
        />
      </div>
    </div>
  );
}
