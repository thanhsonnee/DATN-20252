import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { authApi } from "@/api/client";

type State = "loading" | "success" | "error";

export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [state, setState] = useState<State>("loading");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setState("error");
      setErrorMsg("No verification token found in URL.");
      return;
    }
    authApi
      .verifyEmail(token)
      .then(() => setState("success"))
      .catch((err: any) => {
        setState("error");
        setErrorMsg(err.response?.data?.detail ?? "Verification failed.");
      });
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-blue-100">
      <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-sm text-center">
        {state === "loading" && (
          <>
            <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-600 text-sm">Verifying email...</p>
          </>
        )}

        {state === "success" && (
          <>
            <div className="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
              <svg className="w-7 h-7 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-xl font-bold text-gray-900 mb-2">Verification successful!</h2>
            <p className="text-sm text-gray-500 mb-6">Your account has been activated. You can log in now.</p>
            <button
              onClick={() => navigate("/login")}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 rounded-lg text-sm"
            >
              Log in
            </button>
          </>
        )}

        {state === "error" && (
          <>
            <div className="w-14 h-14 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
              <svg className="w-7 h-7 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h2 className="text-xl font-bold text-gray-900 mb-2">Verification failed</h2>
            <p className="text-sm text-red-500 mb-6">{errorMsg}</p>
            <button
              onClick={() => navigate("/login")}
              className="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium py-2 rounded-lg text-sm"
            >
              Back to login
            </button>
          </>
        )}
      </div>
    </div>
  );
}
