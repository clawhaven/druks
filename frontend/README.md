# Druks frontend

The frontend is the React 19 dashboard bundled into the Druks backend image. In
production FastAPI serves the built SPA; in development Vite runs separately
and proxies API calls to the backend.

## Commands

From the repository root:

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
```

`build` runs TypeScript project compilation before Vite. CI uses Node 22 and
runs lint, tests, and build.

## Ownership

`src/App.tsx` is the platform shell. It owns:

- the app bar and extension picker
- Settings
- Events and Usage pages
- the optional system-health strip
- shared routing and fallback behavior

Bundled extension UI lives under `src/extensions/<name>/`. Its module calls
`registerExtensionUI()` with routes, navigation, and an optional home path.
Import that module once from `src/extensions/index.ts`; the shell discovers the
registration and does not hardcode the extension name.

Backend and frontend extension discovery are intentionally separate:

- Python entry points load an installed backend extension at runtime.
- React extension modules are compiled into the SPA at build time.

Installing a Python distribution cannot inject JavaScript into an already-built
dashboard. A backend-only extension can still use the platform API, settings,
events, and generic subject read-side; custom pages require a dashboard build
that includes its UI module.

An independently packaged extension has another option: ship static assets in
`<package>/dist/`. Druks serves that standalone frontend at `/app/<name>`
without changing the shared SPA. See the extension-author guide.

## API and live data

Shared requests go through `src/api/client.ts`. The event feed and transcript
components consume server-sent events, with normal HTTP queries supplying the
initial state. Keep API field names aligned with the backend's camelCase
`BaseResponse` serialization.

When changing a backend response contract, update the TypeScript type,
consumer, and focused frontend test in the same change. The
`types:openapi` script is experimental and expects a running server; generated
OpenAPI types are not currently checked into the repository.

## Development topology

Start Postgres, Redis, the backend, and Vite using
[the development guide](../docs/development.md). For a production-like static
asset check, run `npm --prefix frontend run build` and then start the backend;
the application serves the repository-root `dist/` when it exists.
