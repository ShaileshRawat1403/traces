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
  render,
  showHeader = true,
}: {
  name: string;
  title: string;
  intro: ReactNode;
  fetcher: (repoId: string, sha: string) => Promise<T>;
  /** Renderer for the contract shape. Without one, a 200 says the screen is not built yet. */
  render?: (data: T) => ReactNode;
  showHeader?: boolean;
}) {
  const { repoId = "", sha = "" } = useParams();
  const q = useQuery({ queryKey: keys.view(name, repoId, sha), queryFn: () => fetcher(repoId, sha) });
  return (
    <>
      {showHeader ? <PageHeader title={title}>{intro}</PageHeader> : null}
      {q.isPending ? (
        <Loading label={`Loading ${title}`} />
      ) : q.isError ? (
        <ErrorState error={q.error} what={title} />
      ) : render ? (
        render(q.data)
      ) : (
        <Card>
          <p role="status">The API now serves {title.toLowerCase()} for this snapshot. Its screen is scheduled for the next UI checkpoint; nothing is rendered from it here yet.</p>
        </Card>
      )}
    </>
  );
}
