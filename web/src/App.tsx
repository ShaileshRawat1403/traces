import { QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useState } from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { makeQueryClient } from "./api/queries";
import { AppShell } from "./app/AppShell";
import { SnapshotLayout } from "./app/SnapshotLayout";
import { AskPage } from "./features/ask/AskPage";
import { ClaimsPage } from "./features/claims/ClaimsPage";
import { ClaimPage } from "./features/evidence/ClaimPage";
import { JobPage } from "./features/jobs/JobPage";
import { Home } from "./features/repos/Home";
import { RepoPage } from "./features/repos/RepoPage";
import { SettingsPage } from "./features/settings/SettingsPage";
import { SourcePage } from "./features/source/SourcePage";
import { TracePage } from "./features/trace/TracePage";
import { OverviewPage } from "./features/views/OverviewPage";
import { HistoryPage } from "./features/history/HistoryPage";
import { ComponentsPage, RoutesPage } from "./features/views/simpleViews";
import { Loading } from "./ui/States";

// Cytoscape is only downloaded when the graph route opens.
const GraphPage = lazy(() => import("./features/graph/GraphPage"));

function NotFound() {
  return (
    <main id="main" tabIndex={-1} className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="mt-2">
        <Link to="/">Go to repositories</Link>
      </p>
    </main>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Home />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="jobs/:jobId" element={<JobPage />} />
        <Route path="r/:repoId" element={<RepoPage />} />
        <Route path="r/:repoId/s/:sha" element={<SnapshotLayout />}>
          <Route index element={<OverviewPage />} />
          <Route path="components" element={<ComponentsPage />} />
          <Route path="routes" element={<RoutesPage />} />
          <Route
            path="graph"
            element={
              <Suspense fallback={<Loading label="Loading graph view" />}>
                <GraphPage />
              </Suspense>
            }
          />
          <Route path="trace" element={<TracePage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="ask" element={<AskPage />} />
          <Route path="claims" element={<ClaimsPage />} />
          <Route path="review" element={<ClaimsPage reviewer />} />
          <Route path="claim/:claimId" element={<ClaimPage />} />
          <Route path="source" element={<SourcePage />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

export function App() {
  const [qc] = useState(makeQueryClient);
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
