/**
 * Algorithm upload modal.
 * Step 1: edit plugin.py entry point.
 * Step 2: choose VRP variant + confirm metrics.
 */
import { useState } from "react";
import { X, ChevronDown, ChevronRight, FileCode, CheckCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { VRP_VARIANTS, VARIANT_METRICS } from "@/constants/vrpVariants";

interface Props {
  files: File[];
  onConfirm: (files: File[], pluginCode: string, vrpVariant: string, selectedMetrics: string[]) => void;
  onCancel: () => void;
  uploading: boolean;
}

function buildTemplate(folderName: string, fileList: File[]): string {
  const pyFiles = fileList.filter((f) => {
    const rel = (f as any).webkitRelativePath || f.name;
    return rel.endsWith(".py");
  });
  const otherFiles = fileList
    .slice(0, 8)
    .map((f) => {
      const rel = (f as any).webkitRelativePath || f.name;
      return rel.split("/").slice(1).join("/") || f.name;
    })
    .filter(Boolean);

  if (pyFiles.length > 0) {
    const first = (pyFiles[0] as any).webkitRelativePath || pyFiles[0].name;
    const rel = first.split("/").slice(1).join("/") || first;
    return `# Python file already present in folder: ${rel}
# If that file already has get_name, get_description, run → delete this content and edit that file directly.
# Or keep this plugin.py as the entry point and import from that file.

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

# from ${rel.replace(".py", "")} import ...

def get_name() -> str:
    return "${folderName}"


def get_description() -> str:
    return "Description for algorithm ${folderName}"


def run(instance, time_limit_sec: float, seed: int, **kwargs):
    raise NotImplementedError("Implement run() here")
`;
  }

  const fileListComment = otherFiles.length > 0
    ? "\n# Files in folder:\n" + otherFiles.map((f) => `#   ${f}`).join("\n") + "\n"
    : "";

  return `import subprocess
from pathlib import Path
${fileListComment}
def get_name() -> str:
    return "${folderName}"


def get_description() -> str:
    return "Algorithm ${folderName}"


def run(instance, time_limit_sec: float, seed: int, **kwargs):
    """
    Call a binary/script in this folder.
    Example with a compiled C++ binary:
    """
    here = Path(__file__).parent
    # binary = here / "main"  # or your binary name
    # result = subprocess.run(
    #     [str(binary), str(time_limit_sec), str(seed)],
    #     capture_output=True, text=True, timeout=time_limit_sec + 5
    # )
    raise NotImplementedError("Implement run() to call binary/script in this folder")
`;
}

type Step = 1 | 2;

export default function AlgorithmUploadModal({ files, onConfirm, onCancel, uploading }: Props) {
  const { t } = useTranslation();
  const folderName = (() => {
    const rel = (files[0] as any)?.webkitRelativePath || "";
    return rel.split("/")[0] || files[0]?.name || "my_algorithm";
  })();

  const [step, setStep] = useState<Step>(1);
  const [pluginCode, setPluginCode] = useState(() => buildTemplate(folderName, files));
  const [showFiles, setShowFiles] = useState(false);

  // Step 2 state
  const [variant, setVariant] = useState("");
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([]);

  const handleVariantChange = (v: string) => {
    setVariant(v);
    setSelectedMetrics(VARIANT_METRICS[v]?.map((m) => m.key) ?? []);
  };

  const toggleMetric = (key: string) => {
    setSelectedMetrics((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  const handleSubmit = () => {
    const blob = new Blob([pluginCode], { type: "text/x-python" });
    const pluginFile = new File([blob], `${folderName}/plugin.py`, { type: "text/x-python" });
    const otherFiles = files.filter((f) => {
      const rel = ((f as any).webkitRelativePath || f.name).replace("\\", "/");
      const filename = rel.split("/").pop() ?? "";
      return filename !== "plugin.py";
    });
    onConfirm([...otherFiles, pluginFile], pluginCode, variant, selectedMetrics);
  };

  const fileCount = files.length;
  const previewFiles = files.slice(0, 12);
  const availableMetrics = VARIANT_METRICS[variant] ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl mx-4 flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b shrink-0">
          <div>
            <h3 className="font-semibold text-gray-900">{t("algorithms.uploadModal.title")}</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {t("algorithms.uploadModal.folderInfo")} <span className="font-mono font-medium">{folderName}</span>
              {" "}· {fileCount} {t("algorithms.uploadModal.fileCount")}
            </p>
          </div>
          <button onClick={onCancel} disabled={uploading}
            className="p-1.5 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100">
            <X size={18} />
          </button>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-0 px-5 py-2 border-b bg-gray-50 shrink-0">
          {[
            { n: 1, label: t("algorithms.uploadModal.step1Label") },
            { n: 2, label: t("algorithms.uploadModal.step2Label") },
          ].map(({ n, label }, i) => (
            <div key={n} className="flex items-center gap-2">
              {i > 0 && <div className="w-8 h-px bg-gray-300 mx-1" />}
              <button
                onClick={() => n < step ? setStep(n as Step) : undefined}
                className="flex items-center gap-1.5"
              >
                <span className={`w-5 h-5 rounded-full text-xs font-bold flex items-center justify-center
                  ${step === n ? "bg-blue-600 text-white" : step > n ? "bg-green-500 text-white" : "bg-gray-200 text-gray-500"}`}>
                  {step > n ? "✓" : n}
                </span>
                <span className={`text-xs font-medium ${step === n ? "text-blue-700" : "text-gray-400"}`}>{label}</span>
              </button>
            </div>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {/* ── Step 1: plugin.py editor ── */}
          {step === 1 && (
            <>
              {/* File list toggle */}
              <div>
                <button
                  onClick={() => setShowFiles((v) => !v)}
                  className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700"
                >
                  {showFiles ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                  {showFiles ? t("algorithms.uploadModal.hideFiles") : t("algorithms.uploadModal.showFiles")}{" "}
                  {t("algorithms.uploadModal.fileListToggle")}
                </button>
                {showFiles && (
                  <div className="mt-2 bg-gray-50 rounded-lg p-3 max-h-32 overflow-y-auto">
                    {previewFiles.map((f, i) => {
                      const rel = ((f as any).webkitRelativePath || f.name).split("/").slice(1).join("/") || f.name;
                      return (
                        <div key={i} className="font-mono text-xs text-gray-600 py-0.5">{rel}</div>
                      );
                    })}
                    {fileCount > 12 && (
                      <div className="text-xs text-gray-400 pt-1">
                        {t("algorithms.uploadModal.moreFiles", { count: fileCount - 12 })}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Entry point editor */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <FileCode size={15} className="text-blue-600" />
                  <span className="text-sm font-medium text-gray-800">
                    {t("algorithms.uploadModal.entryLabel")} <span className="font-mono text-blue-600">plugin.py</span>
                  </span>
                  <span className="text-xs text-gray-400 ml-1">{t("algorithms.uploadModal.entryNote")}</span>
                </div>
                <textarea
                  value={pluginCode}
                  onChange={(e) => setPluginCode(e.target.value)}
                  spellCheck={false}
                  className="w-full font-mono text-xs bg-gray-900 text-green-300 rounded-lg p-4
                    border border-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500
                    resize-none leading-5"
                  style={{ minHeight: "260px" }}
                />
                <p className="text-xs text-gray-400 mt-1">
                  {t("algorithms.uploadModal.requiredFns")}{" "}
                  <span className="font-mono">get_name()</span>,{" "}
                  <span className="font-mono">get_description()</span>,{" "}
                  <span className="font-mono">run(instance, time_limit_sec, seed, **kwargs)</span>
                </p>
              </div>
            </>
          )}

          {/* ── Step 2: VRP variant + metrics ── */}
          {step === 2 && (
            <div className="space-y-5">
              {/* Variant picker */}
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
                        className={`text-left px-3 py-2.5 rounded-lg border text-sm transition-colors
                          ${active
                            ? "border-blue-500 bg-blue-50 text-blue-800"
                            : "border-gray-200 hover:border-gray-300 text-gray-700"}`}
                      >
                        <span className="font-semibold">{v.label}</span>
                        <span className="block text-xs text-gray-500 mt-0.5">{v.desc}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Metrics picker */}
              {variant && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                    {t("algorithms.metricsStep2")}
                  </p>
                  <div className="space-y-2">
                    {availableMetrics.map((m) => {
                      const checked = selectedMetrics.includes(m.key);
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
                  <p className="text-xs text-gray-400 mt-2">
                    {t("algorithms.metricsSelected", { count: selectedMetrics.length, total: availableMetrics.length })}
                  </p>
                </div>
              )}

              {!variant && (
                <div className="flex items-center gap-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <CheckCircle size={14} className="text-yellow-500 shrink-0" />
                  <p className="text-xs text-yellow-700">{t("algorithms.uploadModal.variantRequired")}</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between gap-3 px-5 py-4 border-t shrink-0">
          <button onClick={onCancel} disabled={uploading}
            className="px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50">
            {t("btn.cancel")}
          </button>

          <div className="flex gap-2">
            {step === 2 && (
              <button
                onClick={() => setStep(1)}
                disabled={uploading}
                className="px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
              >
                {t("btn.back")}
              </button>
            )}

            {step === 1 && (
              <button
                onClick={() => setStep(2)}
                disabled={!pluginCode.trim()}
                className="px-5 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 font-medium"
              >
                {t("btn.next")}
              </button>
            )}

            {step === 2 && (
              <button
                onClick={handleSubmit}
                disabled={uploading || !variant}
                className="px-5 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 font-medium"
              >
                {uploading ? t("btn.uploading") : t("btn.uploadAlgo")}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
