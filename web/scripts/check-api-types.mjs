// Fails when src/api/schema.d.ts is not what openapi-typescript generates from docs/contracts/openapi.json.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const out = join(mkdtempSync(join(tmpdir(), "traces-api-")), "schema.d.ts");
execFileSync(process.execPath, ["node_modules/openapi-typescript/bin/cli.js", "../docs/contracts/openapi.json", "-o", out], { stdio: "inherit" });
if (readFileSync(out, "utf8") !== readFileSync("src/api/schema.d.ts", "utf8")) {
  console.error("src/api/schema.d.ts is stale: run `npm run gen:api` and commit it");
  process.exit(1);
}
console.log("api types are current");
