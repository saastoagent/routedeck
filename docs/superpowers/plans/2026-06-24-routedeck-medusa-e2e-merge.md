# RouteDeck Medusa E2E Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the useful fresh Medusa E2E/live-proof worktree into the current RouteDeck Medusa implementation without regressing the cleaner product-native chat UI.

**Architecture:** Treat `D:\Dev\AI Projects\agent-core` on `saastoagent` as the product/UI/runtime base. Treat `C:\w\rd-medusa-e2e` as a source for verification assets, live-runtime startup, and configuration isolation only. Do not wholesale copy `App.tsx`, `styles.css`, or backend projection code from the E2E worktree because those files are older and leak projection/proof labels into the product UI.

**Tech Stack:** Python 3.11, FastAPI, Uvicorn, httpx, LangGraph, OpenAI chat model config, React 19, TypeScript, Vite, Vitest, Playwright, Docker Medusa Store API.

---

## Current Baseline

- Main implementation: `D:\Dev\AI Projects\agent-core`, branch `saastoagent`, commit `6dbe0d5e`.
- E2E worktree: `C:\w\rd-medusa-e2e`, branch `codex/routedeck-medusa-fresh-e2e`, commit `2dfd0f72`, dirty.
- Current app URL: `http://127.0.0.1:5198/`, backend `http://127.0.0.1:8098/`.
- E2E comparison URL: `http://127.0.0.1:5298/`, backend `http://127.0.0.1:8198/`.
- Current app is more aligned to product UI vision.
- E2E worktree is more aligned to verification vision.

## Merge Rule

Port these from `C:\w\rd-medusa-e2e`:

- `agent-lab-powered-projects/routedeck/docs/medusa-fresh-e2e-contract.md`
- `agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/playwright.config.ts`
- `agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/e2e/fresh-medusa-contract.spec.ts`
- `agent-lab-powered-projects/routedeck/examples/medusa-agent/backend/tests/test_real_runtime_boundary.py`
- `agent-lab-powered-projects/routedeck/examples/medusa-agent/scripts/start-real-runtime.ps1`
- selected package metadata for `@playwright/test` and `e2e:contract`
- selected env isolation behavior from backend `core/config.py`

Do not port these wholesale:

- `examples/medusa-agent/frontend/src/App.tsx`
- `examples/medusa-agent/frontend/src/styles.css`
- `examples/medusa-agent/backend/services/routedeck_projection.py`
- `examples/medusa-agent/backend/services/chat_service.py`

Those files contain useful ideas but are older than the current `saastoagent` implementation.

## File Structure

Modify:

- `agent-lab-powered-projects/routedeck/examples/medusa-agent/backend/core/config.py`
  - Add E2E env aliases and env-file disable switch while preserving current Store API projection schema.
- `agent-lab-powered-projects/routedeck/examples/medusa-agent/backend/services/medusa_catalog.py`
  - Update missing-config messaging to mention both current and E2E env variable names.
- `agent-lab-powered-projects/routedeck/examples/medusa-agent/backend/tests/test_medusa_catalog.py`
  - Add tests for E2E env aliases and no fake product fallback.
- `agent-lab-powered-projects/routedeck/examples/medusa-agent/backend/tests/test_real_runtime_boundary.py`
  - Port and adapt real-runtime guard tests from the E2E worktree.
- `agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/package.json`
  - Add `e2e:contract` script and `@playwright/test`.
- `agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/package-lock.json`
  - Update through `npm install` after package edits.
- `agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/playwright.config.ts`
  - Port and adapt the multi-server E2E config.
- `agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/e2e/fresh-medusa-contract.spec.ts`
  - Port and update assertions to current cleaner UI.
- `agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/src/App.test.tsx`
  - Add or adjust component tests that preserve product-native surface wording.
- `agent-lab-powered-projects/routedeck/examples/medusa-agent/scripts/start-real-runtime.ps1`
  - Port the real runtime startup script and add `PYTHONPATH`.
- `agent-lab-powered-projects/routedeck/docs/medusa-fresh-e2e-contract.md`
  - Port and update status language for the current merge target.
- `agent-lab-powered-projects/routedeck/context.md`
- `agent-lab-powered-projects/routedeck/test_index/README.md`
- `agent-lab-powered-projects/routedeck/architecture/code-map.md`
  - Update after implementation only if the new files are accepted.

Do not modify:

- `routedeck_core/*`
- `routedeck_langgraph/*`
- `react/src/*`

unless an implementation task proves a missing product-neutral primitive. If that happens, stop and ask for approval before framework changes.

---

### Task 0: Safety Snapshot

**Files:**
- Read only: both worktrees

- [ ] **Step 1: Confirm current checkout state**

Run:

```powershell
git -C "D:\Dev\AI Projects\agent-core" status --short --branch
git -C "C:\w\rd-medusa-e2e" status --short --branch
git -C "D:\Dev\AI Projects\agent-core" worktree list
```

Expected:

- Main checkout is `saastoagent`.
- E2E worktree is `codex/routedeck-medusa-fresh-e2e`.
- Do not reset or clean either worktree.

- [ ] **Step 2: Create an implementation branch from current main checkout**

Run:

```powershell
git -C "D:\Dev\AI Projects\agent-core" switch -c codex/routedeck-medusa-e2e-merge
```

Expected: branch is created from current `saastoagent`.

- [ ] **Step 3: Record source-of-truth rule in the task notes**

Use this rule for all later choices:

```text
Current checkout wins product UI and projection schema.
E2E worktree wins verification harness and live-runtime startup discipline.
```

- [ ] **Step 4: Commit nothing**

Expected: no files changed yet.

---

### Task 1: Port Fresh E2E Contract Doc

**Files:**
- Create: `agent-lab-powered-projects/routedeck/docs/medusa-fresh-e2e-contract.md`
- Modify: `agent-lab-powered-projects/routedeck/test_index/README.md`

- [ ] **Step 1: Copy the contract doc into the current checkout**

Run:

```powershell
Copy-Item -LiteralPath "C:\w\rd-medusa-e2e\agent-lab-powered-projects\routedeck\docs\medusa-fresh-e2e-contract.md" `
  -Destination "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\docs\medusa-fresh-e2e-contract.md"
```

- [ ] **Step 2: Edit the status paragraph**

Set the top status to:

```markdown
Status: active merge target for the current Medusa RouteDeck reference line.
The current product UI in `examples/medusa-agent` remains the implementation
base; this contract defines the live E2E gate that must be ported from
`C:\w\rd-medusa-e2e`.
```

- [ ] **Step 3: Keep the matrix but update wording that overstates readiness**

Keep `MFE-000` through `MFE-008`. If a row says the latest live run has already passed, change it to say the matrix is the target gate for this merge.

- [ ] **Step 4: Update the validation index**

In `agent-lab-powered-projects/routedeck/test_index/README.md`, add a row:

```markdown
| Medusa fresh E2E contract | `cd examples/medusa-agent/frontend && npm run e2e:contract` | Live browser proof for chat-first Medusa, split assistant/state streams, Store API grounding, missing-config honesty, no write behavior, and no `/api/routedeck/*` product routes. | Medusa reference example; tests and validation harness. |
```

- [ ] **Step 5: Commit**

Run:

```powershell
git add agent-lab-powered-projects/routedeck/docs/medusa-fresh-e2e-contract.md agent-lab-powered-projects/routedeck/test_index/README.md
git commit -m "docs(medusa): add fresh e2e contract target"
```

---

### Task 2: Add Backend Config Compatibility Without Changing Projection Schema

**Files:**
- Modify: `agent-lab-powered-projects/routedeck/examples/medusa-agent/backend/core/config.py`
- Modify: `agent-lab-powered-projects/routedeck/examples/medusa-agent/backend/services/medusa_catalog.py`
- Test: `agent-lab-powered-projects/routedeck/examples/medusa-agent/backend/tests/test_medusa_catalog.py`

- [ ] **Step 1: Add failing tests for env aliases**

Append these tests to `tests/test_medusa_catalog.py`:

```python
def test_settings_accepts_fresh_e2e_store_api_env_names(monkeypatch):
    monkeypatch.setenv("MEDUSA_STORE_API_URL", "http://127.0.0.1:9000")
    monkeypatch.setenv("MEDUSA_STORE_API_PUBLISHABLE_KEY", "pk_fresh")
    monkeypatch.delenv("MEDUSA_BACKEND_URL", raising=False)
    monkeypatch.delenv("MEDUSA_PUBLISHABLE_API_KEY", raising=False)

    from core.config import Settings

    settings = Settings.from_env()

    assert settings.medusa_backend_url == "http://127.0.0.1:9000"
    assert settings.medusa_publishable_api_key == "pk_fresh"


def test_settings_can_ignore_local_env_file_for_e2e(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDUSA_AGENT_DISABLE_ENV_FILE", "1")
    monkeypatch.setenv("MEDUSA_AGENT_MODEL", "gpt-5-nano")

    from core.config import Settings

    settings = Settings.from_env()

    assert settings.medusa_agent_model == "gpt-5-nano"
```

- [ ] **Step 2: Run the tests and verify failure**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\backend"
python -m pytest tests/test_medusa_catalog.py::test_settings_accepts_fresh_e2e_store_api_env_names tests/test_medusa_catalog.py::test_settings_can_ignore_local_env_file_for_e2e -q
```

Expected: first test fails before aliases exist.

- [ ] **Step 3: Implement env aliases in `core/config.py`**

Change `Settings.from_env()` to compute aliases this way:

```python
env_file = {} if _env_bool("MEDUSA_AGENT_DISABLE_ENV_FILE", {}) else _read_local_env(DEFAULT_ENV_PATH)
backend_url = (
    _env_value("MEDUSA_STORE_API_URL", env_file)
    or _env_value("MEDUSA_BACKEND_URL", env_file)
)
publishable_key = (
    _env_value("MEDUSA_STORE_API_PUBLISHABLE_KEY", env_file)
    or _env_value("MEDUSA_PUBLISHABLE_API_KEY", env_file)
)
return cls(
    openai_api_key=_env_value("OPENAI_API_KEY", env_file),
    medusa_agent_model=_env_value("MEDUSA_AGENT_MODEL", env_file, "gpt-5-nano") or "gpt-5-nano",
    medusa_backend_url=backend_url,
    medusa_publishable_api_key=publishable_key,
)
```

Keep the existing field names `medusa_backend_url` and `medusa_publishable_api_key` so current projection code does not churn.

- [ ] **Step 4: Update missing-config message in `medusa_catalog.py`**

Change the message to:

```python
"MEDUSA_STORE_API_URL/MEDUSA_STORE_API_PUBLISHABLE_KEY or MEDUSA_BACKEND_URL/MEDUSA_PUBLISHABLE_API_KEY are required to project the Medusa catalog."
```

- [ ] **Step 5: Run backend catalog tests**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\backend"
python -m pytest tests/test_medusa_catalog.py -q
```

Expected: all catalog tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add agent-lab-powered-projects/routedeck/examples/medusa-agent/backend/core/config.py agent-lab-powered-projects/routedeck/examples/medusa-agent/backend/services/medusa_catalog.py agent-lab-powered-projects/routedeck/examples/medusa-agent/backend/tests/test_medusa_catalog.py
git commit -m "test(medusa): support fresh e2e store api env"
```

---

### Task 3: Port Backend Real-Runtime Boundary Tests

**Files:**
- Create: `agent-lab-powered-projects/routedeck/examples/medusa-agent/backend/tests/test_real_runtime_boundary.py`
- Modify only if required by tests: `agent-lab-powered-projects/routedeck/examples/medusa-agent/backend/services/graph_builder.py`

- [ ] **Step 1: Copy the E2E worktree test**

Run:

```powershell
Copy-Item -LiteralPath "C:\w\rd-medusa-e2e\agent-lab-powered-projects\routedeck\examples\medusa-agent\backend\tests\test_real_runtime_boundary.py" `
  -Destination "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\backend\tests\test_real_runtime_boundary.py"
```

- [ ] **Step 2: Adapt the test to current config field names**

Keep this assertion shape:

```python
def test_default_runtime_model_is_gpt_5_nano(monkeypatch):
    monkeypatch.delenv("MEDUSA_AGENT_MODEL", raising=False)

    from core.config import Settings

    assert Settings.from_env().medusa_agent_model == "gpt-5-nano"
```

Keep the no-temperature assertion:

```python
def test_gpt_5_nano_model_call_does_not_send_sampling_temperature():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "services" / "graph_builder.py").read_text(
        encoding="utf-8"
    )

    assert "temperature=" not in source
```

Delete or rewrite any test that depends on old E2E-only functions such as `medusa_catalog_from_settings` if current `medusa_catalog.py` already covers that behavior.

- [ ] **Step 3: Run the real-runtime boundary test**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\backend"
python -m pytest tests/test_real_runtime_boundary.py -q
```

Expected: pass after Task 2 config aliases.

- [ ] **Step 4: Run backend focused suite**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\backend"
python -m pytest tests/test_medusa_catalog.py tests/test_slice1_chat.py tests/test_slice2_projection.py tests/test_slice3_projection_surfaces.py tests/test_real_runtime_boundary.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add agent-lab-powered-projects/routedeck/examples/medusa-agent/backend/tests/test_real_runtime_boundary.py agent-lab-powered-projects/routedeck/examples/medusa-agent/backend/services/graph_builder.py
git commit -m "test(medusa): add real runtime boundary guards"
```

---

### Task 4: Port Playwright Dependency And Config

**Files:**
- Modify: `agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/package.json`
- Modify: `agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/package-lock.json`
- Create: `agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/playwright.config.ts`

- [ ] **Step 1: Add frontend package script and dependency**

In `package.json`, add:

```json
"e2e:contract": "playwright test -c playwright.config.ts"
```

Add dev dependency:

```json
"@playwright/test": "1.57.0"
```

- [ ] **Step 2: Install to update lockfile**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend"
npm install
```

Expected: `package-lock.json` updates without changing app source.

- [ ] **Step 3: Copy Playwright config from E2E worktree**

Run:

```powershell
Copy-Item -LiteralPath "C:\w\rd-medusa-e2e\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend\playwright.config.ts" `
  -Destination "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend\playwright.config.ts"
```

- [ ] **Step 4: Patch config for current checkout import path**

In every backend `webServer` env block, add:

```ts
PYTHONPATH: "../../..",
```

Keep:

```ts
MEDUSA_AGENT_DISABLE_ENV_FILE: "1",
MEDUSA_AGENT_MODEL: "gpt-5-nano",
```

Use `MEDUSA_STORE_API_URL` and `MEDUSA_STORE_API_PUBLISHABLE_KEY` for the E2E path.

- [ ] **Step 5: Verify Playwright lists tests after spec is added later**

Do not run `npm run e2e:contract` yet because the spec is not ported.

- [ ] **Step 6: Commit**

Run:

```powershell
git add agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/package.json agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/package-lock.json agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/playwright.config.ts
git commit -m "test(medusa): add playwright contract harness"
```

---

### Task 5: Port And Adapt Fresh E2E Spec To Current Product UI

**Files:**
- Create: `agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/e2e/fresh-medusa-contract.spec.ts`
- Modify: `agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/src/App.test.tsx`

- [ ] **Step 1: Copy the E2E spec**

Run:

```powershell
New-Item -ItemType Directory -Force -Path "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend\e2e" | Out-Null
Copy-Item -LiteralPath "C:\w\rd-medusa-e2e\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend\e2e\fresh-medusa-contract.spec.ts" `
  -Destination "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend\e2e\fresh-medusa-contract.spec.ts"
```

- [ ] **Step 2: Update MFE-001 to match current UI**

Keep expectations:

```ts
await expect(page.getByRole("heading", { name: "Medusa Agent" })).toBeVisible();
await expect(page.getByRole("textbox", { name: "Message" })).toBeVisible();
await expect(page.getByTestId("medusa-projected-surface")).toHaveCount(0);
await expect(page.getByText("RouteDeck dashboard")).toHaveCount(0);
await expect(page.getByText("command menu")).toHaveCount(0);
```

Do not require the E2E worktree's `New chat` button.

- [ ] **Step 3: Update MFE-002 for current surface wording**

Keep these checks:

```ts
await expect(page).toHaveURL(/\/browse(?:\?|$)/, { timeout: 60_000 });
await expect(page.getByTestId("medusa-projected-surface")).toContainText("Medusa T-Shirt");
await expect(page.getByTestId("medusa-projected-surface")).not.toContainText("Projected product surface");
await expect(page.getByTestId("medusa-projected-surface")).not.toContainText("Browse projected products");
await expect(page.getByTestId("medusa-projected-surface")).not.toContainText("Read-only browse surface");
```

- [ ] **Step 4: Add direct replay coverage**

Add a test:

```ts
test("MFE-009 direct browse deeplink replays the product projection", async ({ page }) => {
  await page.goto("/browse?surface_id=browse.product_list");

  const surface = page.getByTestId("medusa-projected-surface");
  await expect(surface).toContainText("Medusa T-Shirt", { timeout: 30_000 });
  await expect(surface).toContainText("EUR 10.00");
  await expect(page).toHaveURL(/\/browse\?surface_id=browse\.product_list$/);
});
```

- [ ] **Step 5: Update network guards**

Keep the E2E worktree helpers that collect:

```ts
chatRequests
routeStreams
forbiddenRouteDeckCalls
forbiddenWriteCalls
```

Keep the assertions that `/api/routedeck/*` returns `404`.

- [ ] **Step 6: Add App unit test for no product-surface implementation labels**

In `App.test.tsx`, add:

```tsx
it("keeps product surfaces free of projection proof labels", async () => {
  // Arrange the same mocked projection used by existing browse tests.
  // Then assert:
  expect(screen.queryByText("Projected product surface")).not.toBeInTheDocument();
  expect(screen.queryByText("Browse projected products")).not.toBeInTheDocument();
  expect(screen.queryByText("Read-only browse surface")).not.toBeInTheDocument();
});
```

Use the existing test helper style in `App.test.tsx`; do not introduce a second render harness.

- [ ] **Step 7: Run frontend tests**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend"
npm test -- --run
```

Expected: pass.

- [ ] **Step 8: Commit**

Run:

```powershell
git add agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/e2e/fresh-medusa-contract.spec.ts agent-lab-powered-projects/routedeck/examples/medusa-agent/frontend/src/App.test.tsx
git commit -m "test(medusa): port fresh browser contract"
```

---

### Task 6: Port Real Runtime Startup Script

**Files:**
- Create: `agent-lab-powered-projects/routedeck/examples/medusa-agent/scripts/start-real-runtime.ps1`
- Modify: `agent-lab-powered-projects/routedeck/examples/medusa-agent/README.md`

- [ ] **Step 1: Copy the startup script**

Run:

```powershell
New-Item -ItemType Directory -Force -Path "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\scripts" | Out-Null
Copy-Item -LiteralPath "C:\w\rd-medusa-e2e\agent-lab-powered-projects\routedeck\examples\medusa-agent\scripts\start-real-runtime.ps1" `
  -Destination "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\scripts\start-real-runtime.ps1"
```

- [ ] **Step 2: Add RouteDeck package path to backend command**

Patch script before starting backend:

```powershell
$routeDeckRoot = Resolve-Path (Join-Path $exampleRoot "..\..\..")
$env:PYTHONPATH = $routeDeckRoot.Path
```

Keep custom ports:

```powershell
[int]$BackendPort = 8098,
[int]$FrontendPort = 5198,
```

- [ ] **Step 3: Document real runtime command in README**

Add:

```markdown
Real live-gate runtime:

```powershell
$env:OPENAI_API_KEY = "..."
.\scripts\start-real-runtime.ps1
```

The script starts Docker Medusa, reads the publishable Store API key from local
Postgres, disables the backend `.env` file, uses `gpt-5-nano`, and launches the
Medusa Agent backend/frontend against the real Store API.
```

- [ ] **Step 4: Commit**

Run:

```powershell
git add agent-lab-powered-projects/routedeck/examples/medusa-agent/scripts/start-real-runtime.ps1 agent-lab-powered-projects/routedeck/examples/medusa-agent/README.md
git commit -m "chore(medusa): add real runtime startup script"
```

---

### Task 7: Run Focused Validation Matrix

**Files:**
- No source edits unless tests expose a bug.

- [ ] **Step 1: Backend focused suite**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\backend"
python -m pytest tests/test_medusa_catalog.py tests/test_slice1_chat.py tests/test_slice2_projection.py tests/test_slice3_projection_surfaces.py tests/test_real_runtime_boundary.py -q
```

Expected: all pass.

- [ ] **Step 2: Frontend unit/component suite**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend"
npm test -- --run
```

Expected: all pass.

- [ ] **Step 3: Root anti-drift/reference suite**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
python -m pytest tests/test_anti_drift_boundaries.py tests/test_medusa_reference_slice0.py -q
```

Expected: all pass.

- [ ] **Step 4: Fresh E2E contract**

Prerequisites:

```powershell
$env:OPENAI_API_KEY = "..."
$env:MEDUSA_STORE_API_URL = "http://127.0.0.1:9000"
$env:MEDUSA_STORE_API_PUBLISHABLE_KEY = "<publishable key from Docker Postgres>"
```

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend"
npm run e2e:contract
```

Expected:

- MFE-000 through MFE-009 pass.
- Missing Store API app on `5199` shows unavailable catalog.
- Missing OpenAI app on `5200` shows honest key error.
- No product calls under `/api/routedeck/*`.
- No cart/write calls.

- [ ] **Step 5: Commit only if fixes were required**

If validation required source fixes, commit them:

```powershell
git add <changed files>
git commit -m "fix(medusa): satisfy fresh e2e contract"
```

---

### Task 8: Context Architecture Closeout

**Files:**
- Modify: `agent-lab-powered-projects/routedeck/context.md`
- Modify: `agent-lab-powered-projects/routedeck/architecture/code-map.md`
- Modify: `agent-lab-powered-projects/routedeck/test_index/README.md`
- Create: `agent-lab-powered-projects/routedeck/logs/20260624_medusa_e2e_merge_closeout.md`
- Create: `agent-lab-powered-projects/routedeck/context_checkpoints/context_checkpoint_2026-06-24_medusa_e2e_merge.md`

- [ ] **Step 1: Update code map**

In the Medusa reference example row, include:

```text
fresh E2E Playwright contract, real runtime startup, missing-config E2E servers
```

In source globs, ensure these are covered:

```text
examples/medusa-agent/**/playwright.config.ts, examples/medusa-agent/**/e2e/*.ts, examples/medusa-agent/**/scripts/*.ps1
```

- [ ] **Step 2: Update context**

Add:

```markdown
The fresh E2E worktree was merged selectively. The current checkout remains the
product/UI base. The E2E worktree contributed live-gate contract docs,
Playwright coverage, real runtime startup, and env isolation only.
```

- [ ] **Step 3: Write closeout log**

Create `logs/20260624_medusa_e2e_merge_closeout.md` with:

```markdown
# Medusa E2E Merge Closeout

Date: 2026-06-24

## Summary

Merged verification assets from `C:\w\rd-medusa-e2e` into the current
`saastoagent` implementation without replacing the product-native Medusa UI.

## Preserved From Current Checkout

- Cleaner chat-first UI
- Product-native browse cards
- Current `catalog_status` projection schema
- Store API product `image_source`

## Ported From E2E Worktree

- Fresh E2E contract doc
- Playwright E2E matrix
- Real runtime startup script
- E2E env aliases and env-file isolation
- Runtime boundary tests

## Validation

- Backend focused suite: <result>
- Frontend suite: <result>
- Root anti-drift/reference suite: <result>
- Playwright fresh E2E contract: <result>
```

- [ ] **Step 4: Run doc coverage**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
python scripts/check_doc_coverage.py
```

Expected: exit `0`; document advisory warnings in the closeout log.

- [ ] **Step 5: Commit**

Run:

```powershell
git add agent-lab-powered-projects/routedeck/context.md agent-lab-powered-projects/routedeck/architecture/code-map.md agent-lab-powered-projects/routedeck/test_index/README.md agent-lab-powered-projects/routedeck/logs/20260624_medusa_e2e_merge_closeout.md agent-lab-powered-projects/routedeck/context_checkpoints/context_checkpoint_2026-06-24_medusa_e2e_merge.md
git commit -m "docs(medusa): close out e2e merge"
```

---

### Task 9: Final Diff Review

**Files:**
- All changed files

- [ ] **Step 1: Show commit list**

Run:

```powershell
git log --oneline --decorate --max-count=10
```

- [ ] **Step 2: Verify no accidental E2E UI regression strings**

Run:

```powershell
rg -n "Projected product surface|Browse projected products|Read-only browse surface|store-api-fixture|/medusa-products/" agent-lab-powered-projects/routedeck/examples/medusa-agent
```

Expected:

- No runtime frontend hits for projection proof labels.
- No `/medusa-products/*`.
- `store-api-fixture` appears only in explicit tests if kept at all.

- [ ] **Step 3: Verify no product APIs under RouteDeck prefix**

Run:

```powershell
rg -n "/api/routedeck" agent-lab-powered-projects/routedeck/examples/medusa-agent
```

Expected: hits only in tests/docs that assert the route is forbidden.

- [ ] **Step 4: Keep `C:\w\rd-medusa-e2e` until user approves cleanup**

Do not remove the worktree. It is still useful as a comparison backup until the merge is reviewed.

---

## Self-Review

Spec coverage:

- Product UI base preserved: Task 5 and Task 9.
- Fresh E2E contract ported: Task 1 and Task 5.
- Runtime env isolation ported: Task 2 and Task 6.
- Real Store API live gate covered: Task 4, Task 5, Task 7.
- No RouteDeck framework source changes: stated in file structure and Task 9.
- Context architecture closeout covered: Task 8.

Placeholder scan:

- No `TBD`.
- No "implement later".
- Commands and expected outputs are included for each task.

Type consistency:

- Current projection schema remains `catalog_status`.
- Current config field names remain `medusa_backend_url` and `medusa_publishable_api_key`.
- Fresh E2E env names are aliases, not replacement field names.
