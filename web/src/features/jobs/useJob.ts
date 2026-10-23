import { useQuery, useQueryClient } from "@tanstack/react-query";
import { pollJob, type JobPoll } from "../../api/client";
import { isTerminal } from "./phases";

export const JOB_POLL_MS = 1500; // CONTRACTS.md 4.4: poll every 1 to 2 s, no SSE.

/** Polls GET /jobs/{id} with If-None-Match until the job is terminal. 304 answers keep the cached job. */
export function useJob(jobId: string) {
  const qc = useQueryClient();
  const key = ["job", jobId] as const;
  return useQuery({
    queryKey: key,
    queryFn: ({ signal }) => pollJob(jobId, qc.getQueryData<JobPoll>(key), signal),
    refetchInterval: (q) => (q.state.data && isTerminal(q.state.data.job) ? false : q.state.error ? false : JOB_POLL_MS),
    refetchIntervalInBackground: false,
    staleTime: 0,
  });
}
