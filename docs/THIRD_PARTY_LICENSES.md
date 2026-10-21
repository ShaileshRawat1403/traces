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

Web build-time dependencies (vite 8.3.5, @vitejs/plugin-react 6.1.2, typescript 5.9.3, openapi-typescript 7.13.0, @types/react, @types/react-dom and their transitive packages) are not shipped. Their licenses in the lockfile: MIT (40), ISC (3), Apache-2.0 (3), MPL-2.0 (2), BSD-3-Clause (1), Python-2.0 (1), MIT OR CC0-1.0 (1); 25 platform-specific optional packages are not installed on Linux x64.

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
