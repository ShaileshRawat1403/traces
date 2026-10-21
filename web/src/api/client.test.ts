import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, pollJob, qs } from "./client";
import { shouldRetry } from "./queries";

const jobBody = { id: "j1", repo_id: "r", snapshot_id: null, kind: "index", state: "running", phase: "fetching", progress: 0.1, version: 3, created_at: "a", updated_at: "b" };

afterEach(() => vi.unstubAllGlobals());

describe("pollJob ETag handling", () => {
  it("stores the ETag and sends If-None-Match next time; 304 keeps the previous job", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(jobBody), { status: 200, headers: { ETag: '"3"' } }))
      .mockResolvedValueOnce(new Response(null, { status: 304 }));
    vi.stubGlobal("fetch", fetchMock);
    const first = await pollJob("j1");
    expect(first).toMatchObject({ etag: '"3"', notModified: false });
    const second = await pollJob("j1", first);
    expect(second.notModified).toBe(true);
    expect(second.job).toBe(first.job);
    const headers = fetchMock.mock.calls[1]![1].headers as Record<string, string>;
    expect(headers["If-None-Match"]).toBe('"3"');
  });
});

describe("error envelope", () => {
  it("501 becomes ApiError.notImplemented with owner and milestone", async () => {
    const body = { error: { code: "not_implemented", message: "Overview is not implemented in this build", owner: "Traces", milestone: "VIEWS", detail: null } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 501 })));
    const err = await api.overview("r", "s").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).notImplemented).toBe(true);
    expect((err as ApiError).body.owner).toBe("Traces");
  });
  it("non-JSON errors still produce an ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("oops", { status: 500 })));
    const err = (await api.repos().catch((e: unknown) => e)) as ApiError;
    expect(err.status).toBe(500);
    expect(err.notImplemented).toBe(false);
  });
});

describe("qs", () => {
  it("drops empty values and encodes", () => {
    expect(qs({ a: "x y", b: undefined, c: "", d: false, e: 0 })).toBe("?a=x+y&d=false&e=0");
    expect(qs({})).toBe("");
  });
});

describe("shouldRetry", () => {
  const e = (status: number, code = "x") => new ApiError(status, { code, message: "m" });
  it("never retries 4xx or 501, retries 500 and network errors twice", () => {
    expect(shouldRetry(0, e(404))).toBe(false);
    expect(shouldRetry(0, e(422))).toBe(false);
    expect(shouldRetry(0, e(501, "not_implemented"))).toBe(false);
    expect(shouldRetry(0, e(500))).toBe(true);
    expect(shouldRetry(1, new TypeError("fetch failed"))).toBe(true);
    expect(shouldRetry(2, e(500))).toBe(false);
  });
});
