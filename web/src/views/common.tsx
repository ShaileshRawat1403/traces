import { ApiError } from "../api/client";

export const LABEL_TEXT: Record<string, string> = {
  verified: "Verified",
  observed: "Observed",
  inferred: "Inferred",
  rejected: "Rejected",
};

export function ErrorState({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.notImplemented) {
    return (
      <div className="state not-implemented" role="status">
        <strong>Not implemented yet.</strong> {error.body.message}
        {error.body.owner ? ` Owner: ${error.body.owner}` : ""}
        {error.body.milestone ? `, milestone ${error.body.milestone}.` : ""}
      </div>
    );
  }
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div className="state error" role="alert">
      {msg}
    </div>
  );
}
