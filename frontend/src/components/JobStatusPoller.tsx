import { useEffect, useRef, useState } from "react";
import { jobsApi, type JobOut } from "@/api/client";

interface Props {
  jobId: number;
  onDone?: (job: JobOut) => void;
  intervalMs?: number;
}

/**
 * Polls GET /jobs/{id} every `intervalMs` ms until status is done/failed.
 * Returns the latest JobOut (or null while loading).
 */
export function useJobPoller({ jobId, onDone, intervalMs = 2000 }: Props) {
  const [job, setJob] = useState<JobOut | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let active = true;

    const poll = async () => {
      try {
        const { data } = await jobsApi.get(jobId);
        if (!active) return;
        setJob(data);
        if (data.status === "done" || data.status === "failed") {
          clearInterval(timerRef.current!);
          onDone?.(data);
        }
      } catch {
        // ignore transient errors
      }
    };

    poll();
    timerRef.current = setInterval(poll, intervalMs);

    return () => {
      active = false;
      clearInterval(timerRef.current!);
    };
  }, [jobId, intervalMs]);

  return job;
}
