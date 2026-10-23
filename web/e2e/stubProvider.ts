// Local stub AI provider for the chat e2e specs. It runs only inside the Playwright harness, on 127.0.0.1, and never
// calls any real or paid API. Paths under /cors answer with CORS headers like a browser-friendly provider; paths under
// /nocors omit them, like a provider that blocks browser requests.
import { createServer, type IncomingHttpHeaders, type Server } from "node:http";
import type { AddressInfo } from "node:net";

export interface StubRequest {
  method: string;
  path: string;
  headers: IncomingHttpHeaders;
  body: string;
}

export interface StubProvider {
  url: string;
  requests: StubRequest[];
  close: () => Promise<void>;
}

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "content-type, authorization, x-api-key, anthropic-version, anthropic-dangerous-direct-browser-access",
};

export const FORGED_ID = "c_" + "e".repeat(64);

/** First claim id in the fenced evidence block of the prompt the browser sent. */
function firstSentId(body: string): string | null {
  try {
    const j = JSON.parse(body) as { messages?: { content?: string }[] };
    const p = j.messages?.[0]?.content ?? "";
    const block = p.split("<evidence>\n")[1]?.split("\n</evidence>")[0] ?? "";
    return /^\[(c_[0-9a-f]+)\]/.exec(block)?.[1] ?? null;
  } catch {
    return null;
  }
}

export async function startStubProvider(): Promise<StubProvider> {
  const requests: StubRequest[] = [];
  const server: Server = createServer((req, res) => {
    let body = "";
    req.on("data", (c: Buffer) => (body += c.toString("utf8")));
    req.on("end", () => {
      const path = req.url ?? "/";
      requests.push({ method: req.method ?? "", path, headers: req.headers, body });
      const cors = path.startsWith("/cors/") ? CORS : {};
      if (req.method === "OPTIONS") {
        res.writeHead(204, cors).end();
        return;
      }
      const id = firstSentId(body);
      let out: unknown;
      if (path.endsWith("/chat/completions")) {
        out = { choices: [{ message: { role: "assistant", content: `The evidence records this step [${id}]. A second claim [${FORGED_ID}] is cited too.` } }] };
      } else if (path.endsWith("/v1/messages")) {
        out = { content: [{ type: "text", text: "It probably stores tasks somewhere, but I cannot say where." }] };
      } else {
        res.writeHead(404, { ...cors, "Content-Type": "application/json" }).end(JSON.stringify({ error: { message: "no such stub route" } }));
        return;
      }
      res.writeHead(200, { ...cors, "Content-Type": "application/json" }).end(JSON.stringify(out));
    });
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  const { port } = server.address() as AddressInfo;
  return { url: `http://127.0.0.1:${port}`, requests, close: () => new Promise((r) => server.close(() => r())) };
}
