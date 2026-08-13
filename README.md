# Tool Parameter Optimizer

Foxran market plugin that intercepts tool calls before execution and rewrites only explicitly selected prompt-like fields.

## Requirements

- Foxran with the `ToolInvocation` middleware API and exact model routing support.
- At least one configured chat model.

## Build and distribution

The market-installable package is the plugin directory containing `foxran.yaml`,
the Python backend, and the built `index.umd.js`. Rebuild the frontend with:

```powershell
cd web
npm ci
npm run typecheck
npm run build
```

Do not publish `web/node_modules` or Python cache directories. The root manifest
already points Foxran at the generated UMD bundle.

## Data

Rules are stored outside the plugin checkout under `data/extensions/tool_optimizer/rules.json`. Set `FOXRAN_TOOL_OPTIMIZER_DATA_DIR` to override the location.

## Safety defaults

- Fail-open per rule unless `fail_call` is selected.
- Sensitive fields are denied.
- Only prompt-like strings and string arrays are editable without advanced mode.
- URLs and `url-...` capability references are preserved.
- Run history stores hashes and changed paths, not argument contents.
