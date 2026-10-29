# Web dependencies and licenses

Owner: Traces UI. Every dependency added to `web/` is listed here with its license and why it is used. Versions are pinned exactly in `package.json` and locked in `package-lock.json`; installs run with `npm ci --ignore-scripts`.

Checked from each package's own `package.json` in `node_modules` on 2026-10-21 (IST).

## Runtime (shipped in the browser bundle)

| Package | Version | License | Why |
| --- | --- | --- | --- |
| react, react-dom | 19.3.1 | MIT | UI (scaffold) |
| react-router-dom | 7.18.4 | MIT | Routing, URL as the source of view state (scaffold) |
| cytoscape | 3.34.4 | MIT | Graph canvas, loaded only on the graph route (scaffold, code-split here) |
| @tanstack/react-query | 5.104.5 | MIT | Server state: caching, job polling with ETag, retry policy. Added in ws/ui-shell |
| @radix-ui/react-dialog | 1.3.1 | MIT | Accessible dialog primitive (focus trap, Escape, aria) for the phone More sheet. Added in ws/ui-shell |
| @radix-ui/react-tabs | 1.2.1 | MIT | Accessible tabs (arrow-key roving focus, aria-selected) for the overview layers. Added in ws/ui-overview |
| shiki, @shikijs/langs, @shikijs/themes | 4.5.0 | MIT | Syntax highlighting of pinned source lines with the JavaScript regex engine (no WASM). Tokens are rendered as React text, never as HTML. Loaded lazily with the source panel; only 17 grammars and one theme are bundled. Added in ws/ui-graph |

ws/ui-chat (BYOK chat) adds no dependency: the consent dialog reuses @radix-ui/react-dialog and the Explain/Chat switch reuses @radix-ui/react-tabs. Provider calls use the browser's own `fetch`, and the e2e stub provider uses Node's built-in `http` module.

Full production tree (`npm ls --omit=dev --all`): 86 packages MIT, 1 package 0BSD (`tslib`, pulled in by Radix), 1 package ISC (`@ungap/structured-clone`, pulled in by Shiki through hast-util-to-html; the UI does not call the HTML path). No copyleft code ships to the browser.

## Build time only (not shipped)

| Package | Version | License | Why |
| --- | --- | --- | --- |
| tailwindcss, @tailwindcss/vite, @tailwindcss/oxide | 4.3.3 | MIT | Design tokens and utility CSS, compiled at build time. Added in ws/ui-shell |
| lightningcss (dependency of Tailwind) | 1.33.0 | MPL-2.0 | CSS transform used by Tailwind at build time. File-level copyleft applies only to modifications of its own files; we use it unmodified as a build tool and ship none of its code |
| typescript | 5.9.3 | Apache-2.0 | Type checking, pinned by D-015 (scaffold) |
| vite, @vitejs/plugin-react | 8.3.5, 6.1.2 | MIT | Dev server and bundler (scaffold) |
| openapi-typescript | 7.13.0 | MIT | Generates `src/api/schema.d.ts` from `docs/contracts/openapi.json` (scaffold) |

## Test only (not shipped)

| Package | Version | License | Why |
| --- | --- | --- | --- |
| vitest | 4.1.12 | MIT | Unit tests. 4.1.x chosen because 5.x requires Node 22, and `engines.node` is `>=20.19` |
| jsdom | 26.1.0 | MIT | DOM for unit tests. 26.x supports Node 20 (27+ do not) |
| @testing-library/react | 16.3.3 | MIT | Component tests (pulls in @testing-library/dom 10.4.2, MIT) |
| @testing-library/user-event | 14.6.8 | MIT | Component interaction tests |
| @playwright/test | 1.64.1 | Apache-2.0 | Browser specs in `e2e/` (Traces Lab owns the shared harness and CI) |
| @axe-core/playwright, axe-core | 4.14.0 | MPL-2.0 | Accessibility checks in the browser specs. Test tooling only, used unmodified |

## Not used, on purpose

- No web fonts from a CDN and no analytics: the app makes no outbound requests except to the Traces API on the same origin.
- No component library beyond Radix primitives; components live in `src/ui/`.

## Scripts

| Command | What it does |
| --- | --- |
| `npm run typecheck` | `tsc --noEmit`, strict |
| `npm test` | Vitest unit and component tests |
| `npm run check:api` | Fails if `src/api/schema.d.ts` differs from the generated OpenAPI types |
| `npm run build` | Typecheck and production build |
| `npm run test:e2e` | Playwright specs against a running app (`TRACES_WEB_URL`, default `http://127.0.0.1:5173`) and an API with at least one snapshot. Run `npx playwright install chromium` once |
