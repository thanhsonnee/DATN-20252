import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { instancesApi, visibilityApi, jobsApi, algorithmsApi, uploadAnalyzeApi, type InstanceInfo, type LLMAnalysis, type AlgorithmOut } from "@/api/client";
import { useAuth } from "@/contexts/AuthContext";
import ConfirmModal from "@/components/ConfirmModal";
import InstanceViewModal from "@/components/InstanceViewModal";
import VisibilityModal from "@/components/VisibilityModal";
import LLMAnalysisReview from "@/components/LLMAnalysisReview";
import {
  ChevronDown, ChevronRight, Eye, Folder, PlayCircle,
  Search, Trash2, Upload, FolderOpen, X, CheckSquare, Square,
  ListChecks, Loader2, Globe, Lock, Users, Settings2, FileArchive,
} from "lucide-react";

// ── Visibility Badge ───────────────────────────────────────────────────────────
function VisibilityBadge({ visibility }: { visibility?: string | null }) {
  if (!visibility || visibility === "public") return null;
  if (visibility === "private")
    return (
      <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
        <Lock size={10} /> Private
      </span>
    );
  if (visibility === "shared")
    return (
      <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-blue-50 text-blue-600">
        <Users size={10} /> Shared
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-green-50 text-green-600">
      <Globe size={10} /> Public
    </span>
  );
}


// ── Batch Run Modal ────────────────────────────────────────────────────────────

interface BatchRunModalProps {
  instances: InstanceInfo[];
  onClose: () => void;
  onClearSelection: () => void;
  onRemove: (path: string) => void;
}

function BatchRunModal({ instances, onClose, onClearSelection, onRemove }: BatchRunModalProps) {
  const navigate = useNavigate();
  const [method, setMethod] = useState("greedy");
  const [pluginAlgorithms, setPluginAlgorithms] = useState<AlgorithmOut[]>([]);

  useEffect(() => {
    algorithmsApi.list().then((r) => setPluginAlgorithms(r.data.filter((a) => a.name !== "ALNS" && a.filename != null))).catch(() => {});
  }, []);
  const [timeLimit, setTimeLimit] = useState(60);
  const [seed, setSeed] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);

  const handleRun = async () => {
    if (instances.length === 0) return;
    setSubmitting(true);
    setProgress({ done: 0, total: instances.length });
    const jobIds: number[] = [];
    let failed = 0;
    for (let i = 0; i < instances.length; i++) {
      try {
        const { data } = await jobsApi.create({
          instance_name: instances[i].name,
          method,
          time_limit_sec: timeLimit,
          seed,
        });
        jobIds.push(data.id);
      } catch {
        failed++;
      }
      setProgress({ done: i + 1, total: instances.length });
    }
    setSubmitting(false);
    if (jobIds.length > 0) {
      toast.success(`Created ${jobIds.length} job${failed > 0 ? ` (${failed} failed)` : ""}`);
      onClearSelection();
      onClose();
      navigate("/jobs");
    } else {
      toast.error("All jobs failed");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b shrink-0">
          <h3 className="font-semibold text-gray-900">Batch Run ({instances.length} instances)</h3>
          <button onClick={onClose} disabled={submitting}
            className="p-1.5 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100">
            <X size={18} />
          </button>
        </div>

        {/* Instance list */}
        <div className="overflow-y-auto flex-1 px-5 py-3">
          <p className="text-xs text-gray-500 mb-2">Instances to run:</p>
          <div className="space-y-1">
            {instances.map((ins) => (
              <div key={ins.path}
                className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
                <span className="font-mono text-sm text-gray-800">{ins.name}</span>
                <button
                  onClick={() => onRemove(ins.path)}
                  disabled={submitting}
                  className="text-gray-300 hover:text-red-500 disabled:opacity-30"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Settings */}
        <div className="px-5 py-4 border-t space-y-4 shrink-0">
          {/* Method */}
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">Method</p>
            <div className="flex flex-wrap gap-2">
              {(["greedy", "regret"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMethod(m)}
                  className={`py-2 px-3 rounded-lg border text-sm font-medium transition
                    ${method === m
                      ? "border-blue-500 bg-blue-50 text-blue-700"
                      : "border-gray-200 text-gray-600 hover:border-gray-300"}`}
                >
                  {m === "greedy" ? "Greedy + ALNS" : "Regret-k + ALNS"}
                </button>
              ))}
              {pluginAlgorithms.map((alg) => (
                <button
                  key={alg.id}
                  type="button"
                  onClick={() => setMethod(alg.name)}
                  className={`py-2 px-3 rounded-lg border text-sm font-medium transition
                    ${method === alg.name
                      ? "border-purple-500 bg-purple-50 text-purple-700"
                      : "border-gray-200 text-gray-600 hover:border-gray-300"}`}
                >
                  {alg.name}
                  <span className="ml-1 text-xs bg-purple-100 text-purple-600 px-1 rounded">Plugin</span>
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-4">
            <div className="flex-1">
              <label className="text-xs font-medium text-gray-600 mb-1 block">Time limit (s)</label>
              <input
                type="number" min={5} max={600} value={timeLimit}
                onChange={(e) => setTimeLimit(Number(e.target.value))}
                disabled={submitting}
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              />
            </div>
            <div className="flex-1">
              <label className="text-xs font-medium text-gray-600 mb-1 block">Seed</label>
              <input
                type="number" min={0} value={seed}
                onChange={(e) => setSeed(Number(e.target.value))}
                disabled={submitting}
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              />
            </div>
          </div>

          {/* Progress */}
          {progress && (
            <div>
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span>Creating jobs...</span>
                <span>{progress.done}/{progress.total}</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-1.5">
                <div
                  className="bg-blue-500 h-1.5 rounded-full transition-all"
                  style={{ width: `${(progress.done / progress.total) * 100}%` }}
                />
              </div>
            </div>
          )}

          <button
            onClick={handleRun}
            disabled={submitting || instances.length === 0}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg text-sm"
          >
            {submitting ? (
              <><Loader2 size={15} className="animate-spin" /> Running...</>
            ) : (
              <><PlayCircle size={15} /> Start {instances.length} job{instances.length > 1 ? "s" : ""}</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function InstancesPage() {
  const { isDatasetProvider, isAlgoTester, isAdmin, user } = useAuth();
  const canUpload = isAlgoTester || isDatasetProvider;
  const canRunJob = isAlgoTester;
  const [rootItems, setRootItems] = useState<InstanceInfo[]>([]);
  const [search, setSearch] = useState("");
  const [uploading, setUploading] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [children, setChildren] = useState<Record<string, InstanceInfo[]>>({});
  const [loadingPath, setLoadingPath] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<InstanceInfo | null>(null);
  const [viewTarget, setViewTarget] = useState<InstanceInfo | null>(null);
  const [pendingFiles, setPendingFiles] = useState<FileList | null>(null);
  const [pendingArchive, setPendingArchive] = useState<File | null>(null);
  const [editTarget, setEditTarget] = useState<InstanceInfo | null>(null);

  // LLM analysis flow state
  const [analyzing, setAnalyzing] = useState(false);
  const [llmResult, setLlmResult] = useState<{
    tempId: string;
    analysis: LLMAnalysis;
    visibility: string;
    sharedWithEmails: string[];
    llmAvailable: boolean;
  } | null>(null);

  // Multi-select state
  const [selected, setSelected] = useState<Map<string, InstanceInfo>>(new Map());
  const [showBatchModal, setShowBatchModal] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const archiveInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  // canDelete: admin, or owner, or dataset_provider on unclaimed (no owner) non-system folders
  const SYSTEM_FOLDERS = ["sartori-dataset", "lilim-dataset", "2e-vrp-pdd-main"];
  const isSystemFolder = (ins: InstanceInfo) =>
    ins.is_folder && SYSTEM_FOLDERS.includes(ins.name);
  const canDelete = (ins: InstanceInfo) => {
    if (isSystemFolder(ins)) return isAdmin;
    if (isAdmin) return true;
    if (ins.uploaded_by_id === user?.user_id) return true;
    // unclaimed (no owner): dataset_provider or algo_tester can delete
    if (ins.uploaded_by_id == null && (isDatasetProvider || isAlgoTester)) return true;
    return false;
  };
  const canEditVisibility = (ins: InstanceInfo) => {
    if (isSystemFolder(ins)) return isAdmin;
    if (isAdmin) return true;
    if (ins.uploaded_by_id === user?.user_id) return true;
    if (ins.uploaded_by_id == null && isDatasetProvider) return true;
    return false;
  };

  const loadRoot = () => {
    instancesApi.list().then((r) => setRootItems(r.data)).catch(() => {});
  };

  useEffect(() => { loadRoot(); }, []);

  const toggleFolder = async (ins: InstanceInfo) => {
    const { path } = ins;
    if (expanded.has(path)) {
      setExpanded((prev) => { const s = new Set(prev); s.delete(path); return s; });
      return;
    }
    if (!children[path]) {
      setLoadingPath(path);
      try {
        const { data } = await instancesApi.list(path);
        setChildren((prev) => ({ ...prev, [path]: data }));
      } catch {
        toast.error("Failed to load list");
        return;
      } finally {
        setLoadingPath(null);
      }
    }
    setExpanded((prev) => new Set(prev).add(path));
  };

  // Step 1: send to analyze endpoint → show LLM review modal
  const doUpload = async (fileList: FileList, visibility: string, sharedWithEmails: string[]) => {
    setAnalyzing(true);
    setPendingFiles(null);
    try {
      const { data } = await uploadAnalyzeApi.dataset(Array.from(fileList), visibility, sharedWithEmails);
      setLlmResult({ tempId: data.temp_id, analysis: data.analysis, visibility, sharedWithEmails, llmAvailable: data.llm_available ?? true });
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? "Phân tích thất bại");
    } finally {
      setAnalyzing(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (folderInputRef.current) folderInputRef.current.value = "";
    }
  };

  // Step 2a: user confirmed LLM analysis → save officially
  const handleLLMConfirm = async () => {
    if (!llmResult) return;
    setUploading(true);
    try {
      await uploadAnalyzeApi.confirm(llmResult.tempId, "dataset", llmResult.analysis);
      toast.success("Dataset đã được upload thành công");
      setChildren({});
      setExpanded(new Set());
      loadRoot();
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? "Confirm thất bại");
    } finally {
      setUploading(false);
      setLlmResult(null);
    }
  };

  // Step 2b: user rejected → delete temp files
  const handleLLMReject = async () => {
    if (!llmResult) return;
    try {
      await uploadAnalyzeApi.reject("dataset", llmResult.tempId);
    } catch { /* best-effort */ }
    setLlmResult(null);
    toast("Upload đã bị hủy", { icon: "🚫" });
  };

  const handleEditVisibility = async (visibility: string, sharedWithEmails: string[]) => {
    if (!editTarget) return;
    try {
      await visibilityApi.updateInstance(editTarget.path, visibility, sharedWithEmails);
      toast.success("Visibility updated");
      setChildren({});
      setExpanded(new Set());
      loadRoot();
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? "Update failed");
    } finally {
      setEditTarget(null);
    }
  };

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    // dataset_provider chooses visibility; algo_tester always private (no modal)
    if (isDatasetProvider && !isAdmin) {
      setPendingFiles(fileList);
    } else {
      doUpload(fileList, "private", []);
    }
  };

  const doUploadArchive = async (file: File, visibility: string, sharedWithEmails: string[]) => {
    setUploading(true);
    try {
      const { data } = await instancesApi.uploadArchive(file, visibility, sharedWithEmails);
      if (data.uploaded.length > 0) toast.success(`Extracted and uploaded ${data.uploaded.length} file${data.uploaded.length > 1 ? "s" : ""}`);
      if (data.skipped.length > 0) toast(`Skipped ${data.skipped.length} existing file${data.skipped.length > 1 ? "s" : ""}`, { icon: "⚠️" });
      if (data.failed?.length > 0) toast.error(`${data.failed.length} invalid file${data.failed.length > 1 ? "s" : ""} (not valid PDPTW format)`);
      setChildren({});
      setExpanded(new Set());
      loadRoot();
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? "Archive upload failed");
    } finally {
      setUploading(false);
      setPendingArchive(null);
      if (archiveInputRef.current) archiveInputRef.current.value = "";
    }
  };

  const handleArchive = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const file = fileList[0];
    if (isDatasetProvider && !isAdmin) {
      setPendingArchive(file);
    } else {
      doUploadArchive(file, "private", []);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await instancesApi.delete(deleteTarget.path);
      toast.success(`Deleted "${deleteTarget.name}"`);
      setChildren((prev) => {
        const next = { ...prev };
        Object.keys(next).forEach((parentPath) => {
          next[parentPath] = next[parentPath].filter((c) => c.path !== deleteTarget.path);
        });
        delete next[deleteTarget.path];
        return next;
      });
      setExpanded((prev) => { const s = new Set(prev); s.delete(deleteTarget.path); return s; });
      // Also remove from selection
      setSelected((prev) => { const m = new Map(prev); m.delete(deleteTarget.path); return m; });
      loadRoot();
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? "Delete failed");
    } finally {
      setDeleteTarget(null);
    }
  };

  const toggleSelect = (ins: InstanceInfo, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelected((prev) => {
      const m = new Map(prev);
      if (m.has(ins.path)) m.delete(ins.path);
      else m.set(ins.path, ins);
      return m;
    });
  };

  const clearSelection = () => setSelected(new Map());

  const selectedList = Array.from(selected.values());

  // Build flat list of <tr> rows recursively
  const buildRows = (items: InstanceInfo[], depth: number): React.ReactElement[] => {
    const rows: React.ReactElement[] = [];
    const indent = depth * 20;

    items.forEach((ins) => {
      if (ins.is_folder) {
        const isExpanded = expanded.has(ins.path);
        const isLoading = loadingPath === ins.path;
        rows.push(
          <tr
            key={`folder-${ins.path}`}
            className="border-b hover:bg-blue-50 cursor-pointer select-none"
            onClick={() => toggleFolder(ins)}
          >
            <td className="py-2 w-8 pl-2">
              {/* no checkbox for folders */}
            </td>
            <td className="py-2" style={{ paddingLeft: `${indent + 4}px` }}>
              <div className="flex items-center gap-2">
                {isLoading ? (
                  <span className="text-gray-400 text-xs">⟳</span>
                ) : isExpanded ? (
                  <ChevronDown size={15} className="text-gray-500 shrink-0" />
                ) : (
                  <ChevronRight size={15} className="text-gray-500 shrink-0" />
                )}
                <Folder size={15} className="text-blue-500 shrink-0" />
                <span className="font-mono font-medium">{ins.name}</span>
                {ins.file_count !== undefined && (
                  <span className="text-xs text-gray-400">({ins.file_count} file)</span>
                )}
                <VisibilityBadge visibility={ins.visibility} />
              </div>
            </td>
            <td className="py-2 text-gray-400">—</td>
            <td className="py-2 text-gray-400">—</td>
            <td className="py-2 text-gray-400">—</td>
            <td className="py-2 text-right">
              <div className="flex items-center justify-end gap-1">
                {canEditVisibility(ins) && (
                  <button
                    onClick={(e) => { e.stopPropagation(); setEditTarget(ins); }}
                    className="p-1 text-gray-400 hover:text-blue-600"
                    title="Edit visibility"
                  >
                    <Settings2 size={15} />
                  </button>
                )}
                {canDelete(ins) && (
                  <button
                    onClick={(e) => { e.stopPropagation(); setDeleteTarget(ins); }}
                    className="p-1 text-gray-400 hover:text-red-600"
                    title="Delete folder"
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
            </td>
          </tr>
        );
        if (isExpanded && children[ins.path]) {
          rows.push(...buildRows(children[ins.path], depth + 1));
        }
      } else {
        const isSelected = selected.has(ins.path);
        rows.push(
          <tr key={`file-${ins.path}`}
            className={`border-b last:border-0 hover:bg-gray-50 ${isSelected ? "bg-blue-50" : ""}`}>
            <td className="py-2 w-8 pl-2">
              {canRunJob && (
                <button
                  onClick={(e) => toggleSelect(ins, e)}
                  className={`text-gray-400 hover:text-blue-600 ${isSelected ? "text-blue-600" : ""}`}
                  title={isSelected ? "Deselect" : "Select for batch run"}
                >
                  {isSelected ? <CheckSquare size={15} className="text-blue-600" /> : <Square size={15} />}
                </button>
              )}
            </td>
            <td className="py-2 font-mono" style={{ paddingLeft: `${indent + 4}px` }}>
              {depth > 0 && <span className="mr-1 text-gray-300">└</span>}
              {ins.name}
            </td>
            <td className="py-2">{ins.num_requests ?? "—"}</td>
            <td className="py-2">{ins.num_vehicles ?? "—"}</td>
            <td className="py-2">{ins.capacity ?? "—"}</td>
            <td className="py-2">
              <div className="flex items-center justify-end gap-1">
                {canRunJob && (
                  <button
                    onClick={() => navigate(`/jobs/new?instance=${ins.name}`)}
                    className="inline-flex items-center gap-1 px-3 py-1 bg-blue-50 text-blue-700 rounded-lg text-xs hover:bg-blue-100"
                  >
                    <PlayCircle size={13} /> Run solver
                  </button>
                )}
                <button
                  onClick={() => setViewTarget(ins)}
                  className="p-1 text-gray-400 hover:text-blue-600"
                  title="View content"
                >
                  <Eye size={15} />
                </button>
                {canDelete(ins) && (
                  <button
                    onClick={() => setDeleteTarget(ins)}
                    className="p-1 text-gray-400 hover:text-red-600"
                    title="Delete file"
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
            </td>
          </tr>
        );
      }
    });
    return rows;
  };

  const filtered = rootItems.filter((i) =>
    i.name.toLowerCase().includes(search.toLowerCase())
  );
  const rows = buildRows(filtered, 0);

  return (
    <div className="pb-24">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Benchmark Instances</h1>
          <p className="text-sm text-gray-500">List of PDPTW benchmark instances</p>
        </div>
        {canUpload && (
          <div className="flex gap-2">
            <input ref={fileInputRef} type="file" accept=".txt,.csv" multiple className="hidden"
              onChange={(e) => handleFiles(e.target.files)} />
            <input ref={folderInputRef} type="file"
              // @ts-expect-error webkitdirectory is non-standard but widely supported
              webkitdirectory="" className="hidden"
              onChange={(e) => handleFiles(e.target.files)} />
            <input ref={archiveInputRef} type="file" accept=".zip,.tar.gz,.tar.bz2,.tar" className="hidden"
              onChange={(e) => handleArchive(e.target.files)} />
            <button onClick={() => fileInputRef.current?.click()} disabled={uploading}
              className="inline-flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50">
              <Upload size={16} /> Upload file
            </button>
            <button onClick={() => folderInputRef.current?.click()} disabled={uploading}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50">
              <FolderOpen size={16} /> {uploading ? "Uploading..." : "Upload folder"}
            </button>
            <button onClick={() => archiveInputRef.current?.click()} disabled={uploading}
              className="inline-flex items-center gap-2 px-4 py-2 border border-blue-300 text-blue-700 rounded-lg text-sm hover:bg-blue-50 disabled:opacity-50">
              <FileArchive size={16} /> Upload archive
            </button>
          </div>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <div className="relative mb-4">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Search instances or folders..."
            className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>

        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 border-b">
              <th className="pb-2 w-8"></th>
              <th className="pb-2">Name</th>
              <th className="pb-2">Requests</th>
              <th className="pb-2">Max Vehicles</th>
              <th className="pb-2">Capacity</th>
              <th className="pb-2"></th>
            </tr>
          </thead>
          <tbody>
            {rows.length > 0 ? rows : (
              <tr>
                <td colSpan={6} className="py-8 text-center text-gray-400">
                  {rootItems.length === 0
                    ? "No instances found in the instances/ directory"
                    : "No matching results"}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Floating selection panel */}
      {selected.size > 0 && canRunJob && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3
          bg-gray-900 text-white rounded-2xl shadow-2xl px-5 py-3">
          <ListChecks size={18} className="text-blue-400 shrink-0" />
          <span className="text-sm font-medium">
            <span className="text-blue-400 font-bold">{selected.size}</span> instance{selected.size > 1 ? "s" : ""} selected
          </span>
          <div className="flex gap-2 ml-2">
            <button
              onClick={clearSelection}
              className="px-3 py-1.5 rounded-lg text-xs text-gray-300 hover:text-white hover:bg-gray-700"
            >
              Clear
            </button>
            <button
              onClick={() => setShowBatchModal(true)}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-xs font-semibold"
            >
              <PlayCircle size={14} /> Batch run
            </button>
          </div>
        </div>
      )}

      <InstanceViewModal
        path={viewTarget?.path ?? null}
        instanceName={viewTarget?.name ?? ""}
        instanceInfo={viewTarget ?? null}
        onClose={() => setViewTarget(null)}
        onRun={(name) => { setViewTarget(null); navigate(`/jobs/new?instance=${name}`); }}
      />

      <ConfirmModal
        open={deleteTarget !== null}
        title={`Delete ${deleteTarget?.is_folder ? "folder" : "file"}`}
        message={`Confirm delete "${deleteTarget?.name}"?${deleteTarget?.is_folder ? " All files inside will be deleted." : ""}`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
        danger
      />

      {showBatchModal && (
        <BatchRunModal
          instances={selectedList}
          onClose={() => setShowBatchModal(false)}
          onClearSelection={clearSelection}
          onRemove={(path) => setSelected((prev) => { const m = new Map(prev); m.delete(path); return m; })}
        />
      )}

      {pendingFiles && (
        <VisibilityModal
          title="Visibility Options"
          subtitle={`${pendingFiles.length} file${pendingFiles.length > 1 ? "s" : ""} to upload`}
          confirmLabel="Upload"
          onConfirm={(vis, emails) => doUpload(pendingFiles, vis, emails)}
          onCancel={() => {
            setPendingFiles(null);
            if (fileInputRef.current) fileInputRef.current.value = "";
            if (folderInputRef.current) folderInputRef.current.value = "";
          }}
        />
      )}

      {pendingArchive && (
        <VisibilityModal
          title="Visibility Options"
          subtitle={`Archive: ${pendingArchive.name}`}
          confirmLabel="Upload"
          onConfirm={(vis, emails) => doUploadArchive(pendingArchive, vis, emails)}
          onCancel={() => {
            setPendingArchive(null);
            if (archiveInputRef.current) archiveInputRef.current.value = "";
          }}
        />
      )}

      {editTarget && (
        <VisibilityModal
          title="Edit Visibility"
          subtitle={`Folder: ${editTarget.name}`}
          initialVisibility={(editTarget.visibility as any) ?? "public"}
          confirmLabel="Save"
          onConfirm={handleEditVisibility}
          onCancel={() => setEditTarget(null)}
        />
      )}

      {/* Analyzing overlay */}
      {analyzing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-2xl px-8 py-6 flex flex-col items-center gap-3">
            <Loader2 size={32} className="text-blue-500 animate-spin" />
            <p className="text-sm font-medium text-gray-700">Groq AI đang phân tích dataset...</p>
            <p className="text-xs text-gray-400">Vui lòng chờ trong giây lát</p>
          </div>
        </div>
      )}

      {/* LLM Analysis Review Modal */}
      {llmResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-xl mx-4 flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between px-5 py-4 border-b shrink-0">
              <div>
                <h3 className="font-semibold text-gray-900">Xác nhận phân tích dataset</h3>
                <p className="text-xs text-gray-500 mt-0.5">Kiểm tra và chỉnh sửa kết quả Groq AI trước khi lưu</p>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-4">
              <LLMAnalysisReview
                analysis={llmResult.analysis}
                onChange={(updated) => setLlmResult({ ...llmResult, analysis: updated })}
                llmAvailable={llmResult.llmAvailable}
                kind="dataset"
              />
            </div>
            <div className="flex justify-between gap-3 px-5 py-4 border-t shrink-0">
              <button
                onClick={handleLLMReject}
                disabled={uploading}
                className="px-4 py-2 text-sm rounded-lg border border-red-300 text-red-600 hover:bg-red-50 disabled:opacity-50"
              >
                Hủy upload
              </button>
              <button
                onClick={handleLLMConfirm}
                disabled={uploading}
                className="px-5 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 font-medium"
              >
                {uploading ? "Đang lưu..." : "Xác nhận & Lưu"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
