# Third-party licenses

Traces is MIT licensed (see `LICENSE`). This file lists third-party software it depends on. Versions are the locked ones (`uv.lock`, `toolchain/package-lock.json`, `web/package-lock.json`); update this file in the PR that adds or bumps a dependency. No GPL or AGPL dependency is used; no GitNexus or Code Maat code is included.

## Indexing toolchain (`toolchain/`, run inside the sandbox, not redistributed)

| Package | Version | License |
| --- | --- | --- |
| @colbymchenry/codegraph | 1.6.2 | MIT |
| @colbymchenry/codegraph-linux-x64 (platform binary, optional dependency) | 1.6.2 | MIT |
| typescript (validator family, Compiler API) | 6.0.3 | Apache-2.0 |

CodeGraph is pinned by npm integrity (`toolchain/package-lock.json`) and recorded in `toolchain/registry_record.json`.

## Web runtime dependencies (shipped in the web bundle)

| Package | Version | License |
| --- | --- | --- |
| react, react-dom | 19.3.1 | MIT |
| scheduler | 0.28.0 | MIT |
| react-router-dom, react-router | 7.18.4 | MIT |
| cookie | 1.1.1 | MIT |
| set-cookie-parser | 2.7.2 | MIT |
| cytoscape | 3.34.4 | MIT |
| @tanstack/react-query, @tanstack/query-core | 5.104.5 | MIT |
| @radix-ui/react-dialog | 1.3.1 | MIT |
| @radix-ui/react-tabs | 1.2.1 | MIT |
| @radix-ui/* helpers (primitive, collection, compose-refs, context, direction, dismissable-layer, focus-guards, focus-scope, id, portal, presence, react-primitive, roving-focus, slot, use-callback-ref, use-controllable-state, use-effect-event, use-is-hydrated, use-layout-effect) | 0.0.5 to 2.2.0 | MIT |
| aria-hidden, react-remove-scroll, react-remove-scroll-bar, react-style-singleton, use-callback-ref, use-sidecar, get-nonce, detect-node-es | locked | MIT |
| tslib | 2.8.1 | 0BSD |
| shiki, @shikijs/core, @shikijs/engine-javascript, @shikijs/engine-oniguruma, @shikijs/primitive, @shikijs/types | 4.5.0 | MIT |
| @shikijs/langs, @shikijs/themes | 4.5.0 | MIT (package); bundled grammars and themes keep their upstream licenses, listed below |
| @shikijs/vscode-textmate | 10.1.0 | MIT |
| oniguruma-to-es, oniguruma-parser, regex, regex-recursion, regex-utilities | locked | MIT |
| hast-util-to-html, hast-util-whitespace, mdast-util-to-hast, micromark-util-* (character, encode, sanitize-uri, symbol, types), unist-util-* (is, position, stringify-position, visit, visit-parents), vfile, vfile-message, devlop, ccount, character-entities-html4, character-entities-legacy, comma-separated-tokens, space-separated-tokens, html-void-elements, property-information, stringify-entities, trim-lines, zwitch, dequal | locked | MIT |
| @ungap/structured-clone | 1.4.0 | ISC |

All 88 non-dev packages in `web/package-lock.json` (checked 2026-10-23 IST at `35499bc`): MIT (86), ISC (1), 0BSD (1). The type-only packages `@types/hast`, `@types/mdast`, `@types/unist`, `@types/react` and `@types/react-dom` (MIT) appear in that set but ship no code.

### Syntax grammars and theme shipped in the bundle

`web/src/features/source/highlight.ts` loads only these. Upstream sources and licenses come from shiki's `tm-grammars` 1.32.22 and `tm-themes` 1.12.12 metadata.

| Asset | Upstream | License |
| --- | --- | --- |
| typescript, tsx, javascript, jsx, python (MagicPython), json, css, html, markdown, shellscript, dockerfile, go, rust, java, sql | microsoft/vscode `extensions/*/syntaxes` | MIT |
| toml | textmate/toml.tmbundle | TextMate bundle permission notice ("Permission to copy, use, modify, sell and distribute this software is granted", as-is, no warranty); no SPDX id upstream |
| yaml | textmate/yaml.tmbundle | same TextMate bundle permission notice; no SPDX id upstream |
| github-dark-high-contrast theme | primer/github-vscode-theme | MIT |

## Web development and test dependencies (not shipped)

vite 8.3.5, @vitejs/plugin-react 6.1.2, typescript 5.9.3, openapi-typescript 7.13.0, tailwindcss and @tailwindcss/vite 4.3.3, vitest 4.1.12, jsdom 26.1.0, @testing-library/react 16.3.3, @testing-library/user-event 14.6.8, @playwright/test 1.64.1 (Apache-2.0), @axe-core/playwright 4.14.0 (MPL-2.0), @types/react, @types/react-dom and their transitive packages. Licenses of the 140 dev packages installed on Linux x64: MIT (113), Apache-2.0 (9), ISC (7), MPL-2.0 (4), BSD-2-Clause (2), BSD-3-Clause (2), MIT-0 (1), Python-2.0 (1), MIT OR CC0-1.0 (1). 50 platform-specific optional packages are not installed on Linux x64. The Playwright-managed Chromium binary is downloaded at test time and is not redistributed.

## Python (runtime)

| Package | Version | License |
| --- | --- | --- |
| fastapi | 0.156.8 | MIT |
| starlette | 1.9.0 | BSD-3-Clause |
| pydantic, pydantic-core | 2.14.1, 2.50.1 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| anyio | 4.15.1 | MIT |
| h11 | 0.16.0 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| annotated-doc, annotated-types, typing-inspection | 0.0.5, 0.8.0, 0.4.4 | MIT |
| typing-extensions | 4.16.0 | PSF-2.0 |
| opentelemetry-api | 1.45.1 | Apache-2.0 |

## Python (development and test only)

pytest 9.1.1 (MIT), pluggy (MIT), iniconfig (MIT), httpx 0.28.1 and httpcore (BSD-3-Clause), certifi (MPL-2.0), ruff 0.17.1 (MIT), mypy 2.4.0 and mypy-extensions, librt, ast-serialize (MIT), pathspec (MPL-2.0), jsonschema 4.26.0, jsonschema-specifications, referencing, rpds-py, attrs (MIT), packaging (Apache-2.0 OR BSD-2-Clause), pygments (BSD-2-Clause).

## Analysis target (not included)

`fastapi/full-stack-fastapi-template` at `b1125d8` (MIT) is fetched into the gitignored cache for the baseline and never committed (see FIXTURES.md).
