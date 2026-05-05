/**
 * Reusable visibility selector modal.
 * Uses email input instead of user dropdown — works for any role.
 */
import { useState, KeyboardEvent } from "react";
import { usersApi } from "@/api/client";
import { X, Plus, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

type VisibilityValue = "public" | "private" | "shared";

interface ResolvedUser {
  email: string;
  id: number;
  full_name: string;
}

interface Props {
  title?: string;
  subtitle?: string;
  initialVisibility?: VisibilityValue;
  initialEmails?: string[];
  confirmLabel?: string;
  accentColor?: string; // tailwind color prefix e.g. "blue" | "purple"
  onConfirm: (visibility: string, sharedWithEmails: string[]) => void;
  onCancel: () => void;
}

export default function VisibilityModal({
  title,
  subtitle,
  initialVisibility = "public",
  initialEmails = [],
  confirmLabel,
  accentColor = "blue",
  onConfirm,
  onCancel,
}: Props) {
  const { t } = useTranslation();
  const [visibility, setVisibility] = useState<VisibilityValue>(initialVisibility);
  const [emailInput, setEmailInput] = useState("");
  const [resolving, setResolving] = useState(false);
  const [resolveError, setResolveError] = useState("");
  const [sharedUsers, setSharedUsers] = useState<ResolvedUser[]>(() =>
    initialEmails.map((e) => ({ email: e, id: -1, full_name: e }))
  );

  const accent = accentColor;

  const resolvedTitle = title ?? t("visibilityModal.defaultTitle");
  const resolvedConfirmLabel = confirmLabel ?? t("visibilityModal.defaultConfirm");

  const addEmail = async () => {
    const email = emailInput.trim().toLowerCase();
    if (!email) return;
    if (sharedUsers.some((u) => u.email === email)) {
      setResolveError(t("visibilityModal.alreadyAdded"));
      return;
    }
    setResolving(true);
    setResolveError("");
    try {
      const { data } = await usersApi.byEmail(email);
      setSharedUsers((prev) => [...prev, { email: data.email, id: data.id, full_name: data.full_name }]);
      setEmailInput("");
    } catch {
      setResolveError(t("visibilityModal.userNotFound"));
    } finally {
      setResolving(false);
    }
  };

  const handleKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") { e.preventDefault(); addEmail(); }
  };

  const removeUser = (email: string) =>
    setSharedUsers((prev) => prev.filter((u) => u.email !== email));

  const handleConfirm = () => {
    onConfirm(visibility, sharedUsers.map((u) => u.email));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4 space-y-4">
        <div>
          <h3 className="font-semibold text-gray-900">{resolvedTitle}</h3>
          {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
        </div>

        {/* Visibility options */}
        <div className="space-y-2">
          {(["public", "private", "shared"] as const).map((v) => (
            <label key={v}
              className={`flex items-center gap-3 p-2.5 border rounded-lg cursor-pointer hover:bg-gray-50
                ${visibility === v ? `border-${accent}-400 bg-${accent}-50/40` : "border-gray-200"}`}>
              <input type="radio" name="vis" value={v} checked={visibility === v}
                onChange={() => setVisibility(v)}
                className={`accent-${accent}-600`} />
              <div>
                <p className="text-sm font-medium text-gray-800">
                  {v === "public"
                    ? t("visibility.public")
                    : v === "private"
                    ? t("visibility.private")
                    : t("visibility.sharedLabel")}
                </p>
                <p className="text-xs text-gray-400">
                  {v === "public"
                    ? t("visibility.publicDesc")
                    : v === "private"
                    ? t("visibility.privateDesc")
                    : t("visibility.sharedDesc")}
                </p>
              </div>
            </label>
          ))}
        </div>

        {/* Email input for shared */}
        {visibility === "shared" && (
          <div>
            <p className="text-xs font-medium text-gray-600 mb-1.5">{t("visibilityModal.addByEmail")}</p>
            <div className="flex gap-2">
              <input
                type="email"
                value={emailInput}
                onChange={(e) => { setEmailInput(e.target.value); setResolveError(""); }}
                onKeyDown={handleKey}
                placeholder={t("visibilityModal.emailPlaceholder")}
                className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button onClick={addEmail} disabled={resolving || !emailInput.trim()}
                className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm disabled:opacity-40 flex items-center gap-1">
                {resolving ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
              </button>
            </div>
            {resolveError && <p className="text-xs text-red-500 mt-1">{resolveError}</p>}

            {/* Added users chips */}
            {sharedUsers.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {sharedUsers.map((u) => (
                  <span key={u.email}
                    className="inline-flex items-center gap-1 text-xs bg-blue-50 text-blue-700 rounded-full px-2.5 py-1 border border-blue-200">
                    <span className="font-medium">{u.full_name !== u.email ? u.full_name : u.email}</span>
                    {u.full_name !== u.email && <span className="text-blue-400">&lt;{u.email}&gt;</span>}
                    <button onClick={() => removeUser(u.email)} className="ml-0.5 text-blue-400 hover:text-blue-700">
                      <X size={11} />
                    </button>
                  </span>
                ))}
              </div>
            )}
            {sharedUsers.length === 0 && (
              <p className="text-xs text-gray-400 mt-1.5">{t("visibilityModal.noUsersAdded")}</p>
            )}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-1">
          <button onClick={onCancel}
            className="px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50">
            {t("btn.cancel")}
          </button>
          <button onClick={handleConfirm}
            className={`px-4 py-2 text-sm rounded-lg bg-${accent}-600 text-white hover:bg-${accent}-700`}>
            {resolvedConfirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
