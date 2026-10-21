import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { Card, Empty, ErrorState, Loading, PageHeader } from "../../ui/States";

export function SourcePage() {
  const { repoId = "", sha = "" } = useParams();
  const [sp] = useSearchParams();
  const path = sp.get("path") ?? "";
  const start = Number(sp.get("start")) || undefined;
  const end = Number(sp.get("end")) || undefined;
  const q = useQuery({ queryKey: ["source", repoId, sha, path, start, end], queryFn: () => api.source(repoId, sha, path, start, end), enabled: !!path });
  return (
    <>
      <PageHeader title="Source at the pinned commit">
        <span className="font-mono text-sm">{path || "no file selected"}</span>
      </PageHeader>
      {!path ? (
        <Empty title="No file selected">Open source from a claim's locations.</Empty>
      ) : q.isPending ? (
        <Loading label="Loading source" />
      ) : q.isError ? (
        <ErrorState error={q.error} what="Source view" />
      ) : (
        <Card>
          <p role="status">The API returned {q.data.lines.length} lines. The full-file viewer is scheduled for the next UI checkpoint; claim pages already show source panels.</p>
        </Card>
      )}
    </>
  );
}
