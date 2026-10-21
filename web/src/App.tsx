import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { api } from "./api/client";
import { Home } from "./views/Home";
import { RepoPage } from "./views/RepoPage";
import { SnapshotPage } from "./views/SnapshotPage";

function ApiStatus() {
  const [status, setStatus] = useState("checking API");
  useEffect(() => {
    api.health().then(
      (h) => setStatus(`API ${h.version}, store migration ${h.store_migration}`),
      (e: unknown) => setStatus(`API unavailable: ${e instanceof Error ? e.message : String(e)}`),
    );
  }, []);
  return <footer>{status}</footer>;
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/r/:repoId" element={<RepoPage />} />
        <Route path="/r/:repoId/s/:sha" element={<SnapshotPage />} />
        <Route path="/r/:repoId/s/:sha/:view" element={<SnapshotPage />} />
        <Route path="*" element={<main>Not found</main>} />
      </Routes>
      <ApiStatus />
    </BrowserRouter>
  );
}
