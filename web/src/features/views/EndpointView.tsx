import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useParams } from "react-router-dom";
import { keys } from "../../api/queries";
import { Card, ErrorState, Loading, PageHeader } from "../../ui/States";

/**
 * A screen whose endpoint is still owned by another milestone. It always calls the real endpoint:
 * a 501 shows the owner and milestone; a 200 says the data arrived but this checkpoint has no renderer for it yet.
 * It never shows placeholder or fixture data.
 */
export function EndpointView<T>({
  name,
  title,
  intro,
  fetcher,
}: {
  name: string;
  title: string;
  intro: ReactNode;
  fetcher: (repoId: string, sha: string) => Promise<T>;
}) {
  const { repoId = "", sha = "" } = useParams();
  const q = useQuery({ queryKey: keys.view(name, repoId, sha), queryFn: () => fetcher(repoId, sha) });
  return (
    <>
      <PageHeader title={title}>{intro}</PageHeader>
      {q.isPending ? (
        <Loading label={`Loading ${title}`} />
      ) : q.isError ? (
        <ErrorState error={q.error} what={title} />
      ) : (
        <Card>
          <p role="status">The API now serves {title.toLowerCase()} for this snapshot. Its screen is scheduled for the next UI checkpoint; nothing is rendered from it here yet.</p>
        </Card>
      )}
    </>
  );
}
