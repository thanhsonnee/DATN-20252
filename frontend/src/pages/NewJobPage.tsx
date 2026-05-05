import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import toast from "react-hot-toast";
import { instancesApi, jobsApi, algorithmsApi, type InstanceInfo, type AlgorithmOut } from "@/api/client";
import { ArrowLeft, Search, X, ChevronDown, UploadCloud } from "lucide-react";
import { useTranslation } from "react-i18next";

function InstancePicker({
  instances,
  value,
  onChange,
  loading,
}: {
  instances: InstanceInfo[];
  value: string;
  onChange: (name: string) => void;
  loading: boolean;
}) {
  const { t } = useTranslation();
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Sync display when value set externally (e.g. from URL param)
  useEffect(() => { setQuery(value); }, [value]);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = query.trim()
    ? instances.filter((i) => i.name.toLowerCase().includes(query.toLowerCase()))
    : instances;

  const select = (ins: InstanceInfo) => {
    onChange(ins.name);
    setQuery(ins.name);
    setOpen(false);
  };

  const clear = () => { onChange(""); setQuery(""); setOpen(false); };

  // Derive folder label from path
  const folderOf = (ins: InstanceInfo) => {
    const parts = ins.path.split("/");
    return parts.length > 1 ? parts.slice(0, -1).join("/") : "";
  };

  return (
    <div ref={ref} className="relative">
      <div
        className={`flex items-center border rounded-lg px-3 py-2 gap-2 bg-white cursor-text
          ${open ? "ring-2 ring-blue-500 border-blue-500" : "border-gray-300"}`}
        onClick={() => { setOpen(true); }}
      >
        <Search size={15} className="text-gray-400 shrink-0" />
        <input
          className="flex-1 text-sm outline-none bg-transparent placeholder-gray-400"
          placeholder={loading ? t("newJob.instanceLoading") : t("newJob.instanceSearch")}
          value={query}
          disabled={loading}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
        />
        {value ? (
          <button type="button" onClick={clear} className="text-gray-400 hover:text-gray-600">
            <X size={14} />
          </button>
        ) : (
          <ChevronDown size={14} className="text-gray-400" />
        )}
      </div>

      {open && (
        <div className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-72 overflow-y-auto">
          {filtered.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-6">{t("newJob.instanceNotFound")}</p>
          ) : (
            filtered.map((ins) => {
              const folder = folderOf(ins);
              return (
                <button
                  type="button"
                  key={ins.path}
                  onClick={() => select(ins)}
                  className={`w-full text-left px-4 py-2.5 hover:bg-blue-50 flex items-center justify-between gap-4
                    ${ins.name === value ? "bg-blue-50 text-blue-700" : "text-gray-800"}`}
                >
                  <span className="font-mono text-sm font-medium">{ins.name}</span>
                  {folder && (
                    <span className="text-xs text-gray-400 truncate max-w-[200px] text-right">
                      {folder}
                    </span>
                  )}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

export default function NewJobPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [instances, setInstances] = useState<InstanceInfo[]>([]);
  const [loadingInstances, setLoadingInstances] = useState(true);

  const [instanceName, setInstanceName] = useState(params.get("instance") ?? "");
  const [method, setMethod] = useState("greedy");
  const [timeLimit, setTimeLimit] = useState(60);
  const [seed, setSeed] = useState(0);
  const [loading, setLoading] = useState(false);
  const [pluginAlgorithms, setPluginAlgorithms] = useState<AlgorithmOut[]>([]);

  useEffect(() => {
    instancesApi
      .listAll()
      .then((r) => setInstances(r.data))
      .catch(() => {})
      .finally(() => setLoadingInstances(false));
    algorithmsApi.list().then((r) => {
      setPluginAlgorithms(r.data.filter((a) => a.name !== "ALNS" && a.filename != null));
    }).catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!instanceName) { toast.error(t("newJob.selectInstance")); return; }
    setLoading(true);
    try {
      const { data } = await jobsApi.create({
        instance_name: instanceName,
        method,
        time_limit_sec: timeLimit,
        seed,
      });
      toast.success(t("newJob.jobCreated", { id: data.id }));
      navigate(`/jobs/${data.id}`);
    } catch (e: any) {
      toast.error(e.response?.data?.detail ?? t("newJob.createFailed"));
    } finally {
      setLoading(false);
    }
  };

  // Show selected instance info
  const selectedInfo = instances.find((i) => i.name === instanceName);

  return (
    <div className="max-w-lg">
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4"
      >
        <ArrowLeft size={16} /> {t("btn.back")}
      </button>

      <h1 className="text-2xl font-bold text-gray-900 mb-6">{t("newJob.title")}</h1>

      {!loadingInstances && instances.length === 0 && (
        <div className="mb-5 flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl px-4 py-4">
          <UploadCloud size={20} className="text-amber-500 shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="font-medium text-amber-800">{t("newJob.noInstancesTitle")}</p>
            <p className="text-amber-700 mt-0.5">
              {t("newJob.noInstancesDesc")}{" "}
              <button
                type="button"
                onClick={() => navigate("/instances")}
                className="underline font-medium hover:text-amber-900"
              >
                {t("newJob.noInstancesLink")}
              </button>{" "}
              {t("newJob.noInstancesSuffix")}
            </p>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 space-y-5">

        {/* Instance picker */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t("newJob.instanceLabel")} <span className="text-red-500">*</span>
          </label>
          <InstancePicker
            instances={instances}
            value={instanceName}
            onChange={setInstanceName}
            loading={loadingInstances}
          />
          {/* Selected instance metadata */}
          {selectedInfo && (
            <div className="mt-2 flex gap-4 text-xs text-gray-500 bg-gray-50 rounded-lg px-3 py-2">
              {selectedInfo.num_requests != null && <span>Requests: <b>{selectedInfo.num_requests}</b></span>}
              {selectedInfo.num_vehicles != null && <span>{t("newJob.instanceMaxVehicles")} <b>{selectedInfo.num_vehicles}</b></span>}
              {selectedInfo.capacity != null && <span>{t("newJob.instanceCapacity")} <b>{selectedInfo.capacity}</b></span>}
            </div>
          )}
        </div>

        {/* Method */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">{t("newJob.methodLabel")}</label>
          <div className="flex flex-col gap-2">
            <label className={`flex items-start gap-3 border rounded-lg px-4 py-3 cursor-pointer transition
              ${method === "greedy" ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}>
              <input type="radio" name="method" value="greedy"
                checked={method === "greedy"} onChange={() => setMethod("greedy")}
                className="mt-0.5 text-blue-600" />
              <div>
                <p className="text-sm font-medium text-gray-800">
                  {t("newJob.methodGreedy")}{" "}
                  <span className="ml-1 text-xs text-blue-600 font-semibold">{t("newJob.methodGreedyBadge")}</span>
                </p>
                <p className="text-xs text-gray-500 mt-0.5">{t("newJob.methodGreedyDesc")}</p>
              </div>
            </label>
            <label className={`flex items-start gap-3 border rounded-lg px-4 py-3 cursor-pointer transition
              ${method === "regret" ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}>
              <input type="radio" name="method" value="regret"
                checked={method === "regret"} onChange={() => setMethod("regret")}
                className="mt-0.5 text-blue-600" />
              <div>
                <p className="text-sm font-medium text-gray-800">{t("newJob.methodRegret")}</p>
                <p className="text-xs text-gray-500 mt-0.5">{t("newJob.methodRegretDesc")}</p>
              </div>
            </label>
            {pluginAlgorithms.map((alg) => (
              <label key={alg.id} className={`flex items-start gap-3 border rounded-lg px-4 py-3 cursor-pointer transition
                ${method === alg.name ? "border-purple-500 bg-purple-50" : "border-gray-200 hover:border-gray-300"}`}>
                <input type="radio" name="method" value={alg.name}
                  checked={method === alg.name} onChange={() => setMethod(alg.name)}
                  className="mt-0.5 text-purple-600" />
                <div>
                  <p className="text-sm font-medium text-gray-800">
                    {alg.name}
                    <span className="ml-2 text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded font-semibold">Plugin</span>
                  </p>
                  {alg.description && <p className="text-xs text-gray-500 mt-0.5">{alg.description}</p>}
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Time limit */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t("newJob.timeLimitLabel")}
          </label>
          <input
            type="number"
            min={5}
            max={600}
            value={timeLimit}
            onChange={(e) => setTimeLimit(Number(e.target.value))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Seed */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">{t("newJob.seedLabel")}</label>
          <input
            type="number"
            min={0}
            value={seed}
            onChange={(e) => setSeed(Number(e.target.value))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <button
          type="submit"
          disabled={loading || !instanceName}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium py-2 rounded-lg text-sm"
        >
          {loading ? t("btn.creating") : t("btn.startRun")}
        </button>
      </form>
    </div>
  );
}
