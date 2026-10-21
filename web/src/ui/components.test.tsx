import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { ApiError, type ClaimSummary, type GraphEdge } from "../api/client";
import { partitionForContext } from "../features/claims/ClaimsPage";
import { drawableEdges } from "../features/graph/graphModel";
import { HiddenCounts } from "./HiddenCounts";
import { ErrorState } from "./States";
import { StatusChip } from "./StatusChip";

afterEach(cleanup);

describe("StatusChip", () => {
  it("renders the API label and a line sample", () => {
    render(<StatusChip status="verified" label="verified" />);
    const chip = screen.getByTestId("status-chip");
    expect(chip.textContent).toContain("Verified");
    expect(chip.querySelector("svg[data-line='solid']")).not.toBeNull();
  });
  it("renders nothing for rejected outside reviewer contexts", () => {
    const { container } = render(<StatusChip status="rejected" label="rejected" />);
    expect(container.textContent).toBe("");
  });
  it("renders Rejected in reviewer context", () => {
    render(<StatusChip status="rejected" label="rejected" context="reviewer" />);
    expect(screen.getByTestId("status-chip").textContent).toContain("Rejected");
  });
  it("missing_location shows Inferred and No source location, dotted", () => {
    render(<StatusChip status="missing_location" label="inferred" flags={["no_source_location"]} />);
    expect(screen.getByTestId("status-chip").textContent).toContain("Inferred");
    expect(screen.getByTestId("status-note").textContent).toBe("No source location");
    expect(screen.getByTestId("status-chip").querySelector("svg[data-line='dotted']")).not.toBeNull();
  });
  it("shows the qualifier verbatim", () => {
    render(<StatusChip status="verified" label="verified" qualifier="statically established persistence path" />);
    expect(screen.getByTestId("qualifier").textContent).toBe("statically established persistence path");
  });
  it("warns on an inconsistent pair instead of choosing", () => {
    render(<StatusChip status="missing_location" label="verified" />);
    expect(screen.getByTestId("status-note").textContent).toMatch(/Warning/);
  });
});

describe("HiddenCounts", () => {
  it("states what is hidden by status and links to the reviewer view", () => {
    render(
      <MemoryRouter>
        <HiddenCounts counts={{ rejected: 12 }} extra={{ unvalidated: 2 }} reviewHref="/review" />
      </MemoryRouter>,
    );
    const el = screen.getByTestId("hidden-counts");
    expect(el.textContent).toContain("14");
    expect(el.textContent).toContain("12 rejected");
    expect(el.textContent).toContain("2 inferred (unvalidated)");
    expect(screen.getByRole("link", { name: "reviewer view" }).getAttribute("href")).toBe("/review");
  });
  it("says nothing is hidden when counts are empty", () => {
    render(<HiddenCounts counts={{}} />);
    expect(screen.getByTestId("hidden-counts").textContent).toMatch(/Nothing hidden/);
  });
});

describe("ErrorState", () => {
  it("names the owner and milestone for 501", () => {
    const err = new ApiError(501, { code: "not_implemented", message: "Graph is not implemented in this build", owner: "Traces", milestone: "VIEWS" });
    render(<ErrorState error={err} what="The architecture graph" />);
    expect(screen.getByTestId("not-available").textContent).toContain("The architecture graph is not available yet");
    expect(screen.getByTestId("owner").textContent).toBe("Traces");
    expect(screen.getByTestId("not-available").textContent).toContain("VIEWS");
  });
  it("shows other errors as alerts", () => {
    render(<ErrorState error={new ApiError(404, { code: "not_found", message: "job x not found" })} />);
    expect(screen.getByRole("alert").textContent).toContain("job x not found");
  });
});

describe("context partitioning", () => {
  const base = { claim_kind: "relationship", kind: "imports", class: "analyzer_inference", evidence_scope: "static", statement: "s", flags: [] as string[] };
  it("claim lists drop rejected outside reviewer views and count them", () => {
    const items: ClaimSummary[] = [
      { ...base, claim_id: "c_a", status: "verified", label: "verified" },
      { ...base, claim_id: "c_b", status: "rejected", label: "rejected" },
    ];
    expect(partitionForContext(items, "default")).toEqual({ shown: [items[0]], hidden: { rejected: 1 } });
    expect(partitionForContext(items, "reviewer").shown).toHaveLength(2);
  });
  it("graph never draws rejected edges", () => {
    const edges: GraphEdge[] = [
      { id: "e1", source: "a", target: "b", kind: "renders", status: "unvalidated", label: "inferred", flags: [] },
      { id: "e2", source: "a", target: "c", kind: "imports", status: "rejected", label: "rejected", flags: [] },
    ];
    const r = drawableEdges({ edges });
    expect(r.edges.map((e) => e.id)).toEqual(["e1"]);
    expect(r.hidden).toEqual({ rejected: 1 });
  });
});
