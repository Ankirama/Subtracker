# C6 Backend Architecture Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a single Markdown audit document at `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md` analysing the 5 largest backend Python files (~5,665 LoC total) and delivering a prioritised refactor roadmap that becomes the proto-spec for sub-project C1.

**Architecture:** Sequential per-file audit passes that each fill in one pre-skeletoned section of the audit document via Edit. Once all 5 per-file sections are populated, three cross-cutting passes append §A (transverse findings), §B (priorities), §C (out-of-scope). Each pass is one commit. A final pass pushes the branch and opens the PR.

**Tech Stack:** Markdown, Bash (grep/find/wc), Read tool (for source code), Edit tool (for incremental section population), Git, gh CLI.

**Source spec:** `docs/superpowers/specs/2026-04-25-c6-backend-architecture-audit-design.md`

**Branch:** `chore/c6-backend-audit` (already created from `origin/main`, spec already committed at `cabc2d5`).

---

## Methodology Note: TDD Adaptation for an Audit

This plan does NOT follow strict TDD. The deliverable is a single analytical document, not executable code. Each task follows a verification-driven pattern:

1. Read the source material (file + tests).
2. Apply the template (provided inline below).
3. Use Edit to replace a placeholder in the audit doc.
4. Run a structural verification (section non-empty, expected sub-headers present, line count plausible).
5. Commit.

For tasks 7-9 (cross-cutting), verification is grep-based: confirm the section addresses the topics required by the spec.

---

## File Structure

A single new document is created and incrementally filled in across 9 commits:

```
docs/superpowers/audits/
└── 2026-04-25-backend-architecture-audit.md
```

| Phase | Section filled | Source material |
|---|---|---|
| Task 1 | Skeleton (all sections as `_Pending …_` placeholders) | — |
| Task 2 | §1 — `api/subscriptions.py` | source + `test_subscriptions_api.py` |
| Task 3 | §2 — `tasks/email_sync.py` | source + grep for any `*email_sync*` test |
| Task 4 | §3 — `api/auth.py` | source + `test_auth.py` |
| Task 5 | §4 — `services/email_templates.py` | source + `test_email_templates.py` |
| Task 6 | §5 — `services/email_service.py` | source + grep for any `*email_service*` test |
| Task 7 | §A — Constats transverses | all 5 sources, grep across them |
| Task 8 | §B — Roadmap priorisée | the 5 sections + §A |
| Task 9 | §C — Out-of-scope | re-read full doc |
| Task 10 | Final review + push + PR | — |

`docs/superpowers/audits/` is a new directory — Task 1 creates it.

---

## Per-File Audit Template (referenced by Tasks 2-6)

Every per-file task uses this exact template, with placeholders replaced by actual analysis content. The auditor does not freelance section names.

```markdown
## §<N> — `<relative path>` — <line count> lines

### Symptômes

[Why this file is god-y. Concrete signals: how many distinct responsibilities,
heterogeneity of imports, depth of nesting, presence of section-comment
"chapters", dispersion of concerns. 3-6 sentences max.]

### Responsabilités identifiées

[Numbered list of "roles" mixed in the file. For each: approximate line range
and one-sentence description. Aim for 3-8 distinct responsibilities.]

1. <role 1> (lines X-Y) — <one-sentence description>
2. <role 2> (lines Y-Z) — <one-sentence description>
3. ...

### Couplages (graph-derived)

- **Imports entrants**: <N> modules import from this file. <Notable / surprising importers, or "_None observed._">
- **Imports sortants**: this file imports from <N> modules. <Cross-layer imports flagged, or "_All within expected layer boundaries._">
- **Centrality**: <god-node? hub of which graphify community? high betweenness? Specific evidence from `grep <module> graphify-out/GRAPH_REPORT.md` if available, or "_Not flagged in GRAPH_REPORT._">

### Couverture tests

- Test file(s) found: <list, or "_None found._">
- Approximate coverage estimate: <percentage based on `grep "^def " source | wc -l` vs `grep "def test_" tests | wc -l` — rough only>
- Refactor safety: **safe** | **risky** | **unknown**
- Justification: <one sentence: why safe/risky/unknown>

### Proposition de découpe

\`\`\`
backend/app/<target dir>/
├── <module-1>.py  (~<N> lines — responsibility)
├── <module-2>.py  (~<N> lines — responsibility)
└── ...
\`\`\`

[2-4 sentence justification of why this split and not another.
Specifically: why these boundaries are stable (won't drift back to god-status).]

### Effort & dépendances

- **Effort**: S / M / L / XL
- **Justification effort**: <one sentence>
- **Bloqueurs**: <other refactors that must happen first, with reference to §N, or "_None._">
- **Bloquant pour**: <other refactors that depend on this one, with reference to §N, or "_None._">
- **Risque**: low / medium / high
- **Justification risque**: <one sentence combining coverage + criticality>
```

T-shirt size definitions:
- **S**: < 2h (mechanical extraction; tests already cover; no caller changes needed)
- **M**: 2-6h (some refactor in callers needed; manageable scope)
- **L**: 6-16h (multi-file restructure; possibly schema/contract changes; non-trivial caller updates)
- **XL**: > 16h (architectural shift; reconsider scope)

If a sub-section genuinely has no content, write `_N/A — <one-sentence reason>._` rather than leaving it empty. Never leave a section header without content.

---

## Tasks

### Task 1: Create audits directory and audit doc skeleton

**Files:**
- Create: `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p docs/superpowers/audits
```

- [ ] **Step 2: Write the skeleton with placeholder sections**

Create `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md` with this exact content:

```markdown
# Backend Architecture Audit — 2026-04-25

> Targeted audit of the 5 largest backend Python modules (~5,665 LoC total).
> Driven by the C decomposition (sub-project C6).
>
> **Spec:** `docs/superpowers/specs/2026-04-25-c6-backend-architecture-audit-design.md`
> **Plan:** `docs/superpowers/plans/2026-04-25-c6-backend-architecture-audit.md`

## Method

This audit applies a fixed per-file template (Symptômes / Responsabilités identifiées / Couplages / Couverture tests / Proposition de découpe / Effort & dépendances) to the 5 largest backend Python files, then synthesises three cross-cutting sections:

- **§A — Constats transverses** — duplication patterns, layer violations, circular imports affecting 2+ files.
- **§B — Roadmap priorisée** — recommended execution order with justification.
- **§C — Out-of-scope** — items noted but not addressed in this audit.

Source data: the source files themselves, their associated test files (if any), and `graphify-out/GRAPH_REPORT.md`. T-shirt sizing (S/M/L/XL), not hour estimates.

## §1 — `backend/app/api/subscriptions.py` — 1441 lines

_Pending audit._

## §2 — `backend/app/tasks/email_sync.py` — 1410 lines

_Pending audit._

## §3 — `backend/app/api/auth.py` — 1191 lines

_Pending audit._

## §4 — `backend/app/services/email_templates.py` — 841 lines

_Pending audit._

## §5 — `backend/app/services/email_service.py` — 782 lines

_Pending audit._

## §A — Constats transverses

_Pending cross-cutting analysis._

## §B — Roadmap priorisée

_Pending prioritisation._

## §C — Out-of-scope

_Pending listing._
```

- [ ] **Step 3: Verify file exists and has 9 top-level sections**

```bash
test -f docs/superpowers/audits/2026-04-25-backend-architecture-audit.md && echo "file OK"
grep -c '^## ' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md
```

Expected: `file OK` and `9` (Method + 5 per-file + §A + §B + §C).

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/audits/2026-04-25-backend-architecture-audit.md
git commit -m "$(cat <<'EOF'
chore(audit): create backend architecture audit skeleton

Lays out the 9-section structure for the C6 audit:
- §1-§5: per-file analyses (skeleton with _Pending audit._ placeholders)
- §A: cross-cutting findings
- §B: priorities/roadmap
- §C: out-of-scope

Subsequent commits fill each section.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Audit §1 — `backend/app/api/subscriptions.py` (1441 lines)

**Files:**
- Read: `backend/app/api/subscriptions.py`
- Read: `backend/tests/test_subscriptions_api.py`
- Reference: `graphify-out/GRAPH_REPORT.md` (grep for `subscriptions`)
- Modify: `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md` (replace `_Pending audit._` under §1)

- [ ] **Step 1: Read the source file in chunks if needed**

Use the Read tool. The file is 1441 lines. Read in two chunks if your tool's default limit is hit:

```
Read backend/app/api/subscriptions.py            # default limit ~2000 lines, should fit
```

If a chunk read is needed:
```
Read backend/app/api/subscriptions.py offset=0 limit=720
Read backend/app/api/subscriptions.py offset=720 limit=722
```

Capture: top-of-file imports, route declarations (`@router.<verb>`), and class/function names. The route declarations and the section comments (look for blocks like `# === <name> ===` or `# --- <name> ---`) are the strongest signals for "responsibilities".

- [ ] **Step 2: Read the test file**

```
Read backend/tests/test_subscriptions_api.py
```

Note: count `def test_` occurrences. This gives a rough coverage signal vs route count.

- [ ] **Step 3: Pull graph data for this module**

```bash
grep -n -A 1 -B 0 'subscriptions\.py\|api/subscriptions\|api\.subscriptions' graphify-out/GRAPH_REPORT.md | head -40
grep -c 'subscriptions' graphify-out/GRAPH_REPORT.md   # rough centrality signal
```

If the GRAPH_REPORT has a "god nodes" or "high centrality" listing, check whether `api/subscriptions.py` (or any of its symbols) is named.

- [ ] **Step 4: Apply the template; replace `_Pending audit._` under §1 with the populated section**

Use Edit on `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md`:

- `old_string`:
  ```
  ## §1 — `backend/app/api/subscriptions.py` — 1441 lines

  _Pending audit._
  ```

- `new_string`: a complete §1 section following the template at the top of this plan. Required sub-section headers: `### Symptômes`, `### Responsabilités identifiées`, `### Couplages (graph-derived)`, `### Couverture tests`, `### Proposition de découpe`, `### Effort & dépendances`.

The "Proposition de découpe" should suggest a target like:

```
backend/app/api/subscriptions/
├── router.py        (~50 lines — wire-up)
├── crud.py          (~? lines — basic CRUD endpoints)
├── reviews.py       (~? lines — review/approval endpoints)
├── filtering.py     (~? lines — search/filter endpoints)
└── ...
```

Adapt directory names and counts to what the actual file's responsibilities reveal.

- [ ] **Step 5: Verify the section is fully populated**

```bash
awk '/^## §1 /,/^## §2 /' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md | head -80 | tail -70
grep -c 'Pending audit' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md
```

Expected: §1 contains all 6 sub-section headers (Symptômes, Responsabilités identifiées, Couplages, Couverture tests, Proposition de découpe, Effort & dépendances) and substantive content under each. `Pending audit` count should now be 4 (was 5; you populated §1).

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/audits/2026-04-25-backend-architecture-audit.md
git commit -m "$(cat <<'EOF'
docs(audit): §1 — api/subscriptions.py (1441 lines)

Identifies <N> responsibilities, proposes split into backend/app/api/subscriptions/
sub-package. Effort: <S/M/L/XL>. Tests: <safe/risky/unknown>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

The commit message body uses placeholders `<N>`, `<S/M/L/XL>`, `<safe/risky/unknown>` — the auditor MUST replace them with the actual values from the audit before committing. Never commit a message containing literal `<N>` etc.

---

### Task 3: Audit §2 — `backend/app/tasks/email_sync.py` (1410 lines)

**Files:**
- Read: `backend/app/tasks/email_sync.py`
- Search: `backend/tests/` for any `*email_sync*` test
- Reference: `graphify-out/GRAPH_REPORT.md`
- Modify: `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md` (replace `_Pending audit._` under §2)

- [ ] **Step 1: Read the source**

The file is 1410 lines.

```
Read backend/app/tasks/email_sync.py
```

If the default limit is hit, chunk:
```
Read backend/app/tasks/email_sync.py offset=0 limit=720
Read backend/app/tasks/email_sync.py offset=720 limit=691
```

Note: this is a Celery task module. Look for `@celery_app.task` (or similar decorators) declarations — each task is a logical unit. Sub-functions called by tasks are also responsibilities.

- [ ] **Step 2: Find associated tests**

```bash
ls backend/tests/ | grep -i 'email_sync\|sync'
find backend -name 'test_*sync*' -o -name '*sync*test*'
```

If no direct test file: note `_None found._` in §Couverture tests — refactor safety = `unknown` or `risky`.

- [ ] **Step 3: Pull graph data**

```bash
grep -n 'email_sync\|tasks/email_sync\|tasks\.email_sync' graphify-out/GRAPH_REPORT.md | head -20
```

- [ ] **Step 4: Apply the template; Edit §2**

Edit `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md`:

- `old_string`:
  ```
  ## §2 — `backend/app/tasks/email_sync.py` — 1410 lines

  _Pending audit._
  ```

- `new_string`: full §2 with all 6 required sub-section headers.

The "Proposition de découpe" should consider that this is a Celery tasks file. A typical split:

```
backend/app/tasks/email_sync/
├── __init__.py       (~10 lines — re-export)
├── orchestrator.py   (~? lines — top-level @celery_app.task)
├── batch_processor.py (~? lines — per-batch logic)
├── classifier_step.py (~? lines — classify stage)
├── extractor_step.py  (~? lines — extract stage)
└── ...
```

Adapt to actual stages observed in the file.

- [ ] **Step 5: Verify**

```bash
awk '/^## §2 /,/^## §3 /' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md | wc -l
grep -c 'Pending audit' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md   # should be 3
```

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/audits/2026-04-25-backend-architecture-audit.md
git commit -m "$(cat <<'EOF'
docs(audit): §2 — tasks/email_sync.py (1410 lines)

Identifies <N> stages of the email sync pipeline conflated in one file,
proposes split into backend/app/tasks/email_sync/ sub-package.
Effort: <S/M/L/XL>. Tests: <safe/risky/unknown>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Replace placeholders before committing.

---

### Task 4: Audit §3 — `backend/app/api/auth.py` (1191 lines)

**Files:**
- Read: `backend/app/api/auth.py`
- Read: `backend/tests/test_auth.py`
- Reference: `graphify-out/GRAPH_REPORT.md`, `docs/architecture/auth.md`
- Modify: `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md` (replace `_Pending audit._` under §3)

- [ ] **Step 1: Read the source**

```
Read backend/app/api/auth.py
```

1191 lines should fit in one read. If not, chunk halves.

Note: this is the auth router. Look for `@router.post`/`@router.get` declarations: login, refresh, register, logout, password reset, email verification, 2FA, IP whitelist, etc. Each endpoint family is a responsibility.

- [ ] **Step 2: Read tests and the existing auth doc**

```
Read backend/tests/test_auth.py
Read docs/architecture/auth.md
```

`docs/architecture/auth.md` documents the *current* model — note any gap between code and doc as input for §C (out-of-scope).

- [ ] **Step 3: Pull graph data**

```bash
grep -n 'api/auth\|api\.auth' graphify-out/GRAPH_REPORT.md | head -20
```

- [ ] **Step 4: Apply the template; Edit §3**

Edit `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md`:

- `old_string`:
  ```
  ## §3 — `backend/app/api/auth.py` — 1191 lines

  _Pending audit._
  ```

- `new_string`: full §3 with all 6 required sub-section headers.

Likely target split (adapt to actual responsibilities):

```
backend/app/api/auth/
├── router.py           (~? lines — wire-up)
├── login.py            (~? lines — login + refresh + logout)
├── registration.py     (~? lines — register + email verify)
├── password.py         (~? lines — reset, change)
├── two_factor.py       (~? lines — 2FA setup/verify)
└── session.py          (~? lines — session mgmt, IP whitelist if applicable)
```

- [ ] **Step 5: Verify**

```bash
grep -c 'Pending audit' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md   # should be 2
```

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/audits/2026-04-25-backend-architecture-audit.md
git commit -m "$(cat <<'EOF'
docs(audit): §3 — api/auth.py (1191 lines)

Identifies <N> auth endpoint families conflated, proposes split into
backend/app/api/auth/ sub-package. Cross-references docs/architecture/auth.md.
Effort: <S/M/L/XL>. Tests: <safe/risky/unknown>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Replace placeholders before committing.

---

### Task 5: Audit §4 — `backend/app/services/email_templates.py` (841 lines)

**Files:**
- Read: `backend/app/services/email_templates.py`
- Read: `backend/tests/test_email_templates.py`
- Reference: `graphify-out/GRAPH_REPORT.md`
- Modify: `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md` (replace `_Pending audit._` under §4)

- [ ] **Step 1: Read source and tests**

```
Read backend/app/services/email_templates.py
Read backend/tests/test_email_templates.py
```

The "templates" service is likely a registry or factory of provider-specific email parsers. Look for: a base class, multiple concrete implementations, dispatcher logic.

- [ ] **Step 2: Pull graph data**

```bash
grep -n 'email_templates\|services/email_templates' graphify-out/GRAPH_REPORT.md | head -20
```

- [ ] **Step 3: Apply the template; Edit §4**

Edit `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md`:

- `old_string`:
  ```
  ## §4 — `backend/app/services/email_templates.py` — 841 lines

  _Pending audit._
  ```

- `new_string`: full §4.

If this file is in fact a registry of N provider templates, the natural split is one file per template:

```
backend/app/services/email_templates/
├── __init__.py     (~10 lines — registry exports)
├── base.py         (~? lines — abstract base + factory)
├── netflix.py      (~? lines — Netflix template)
├── spotify.py      (~? lines — Spotify template)
└── ...
```

Or per-grouping if templates fit into 3-4 categories.

- [ ] **Step 4: Verify**

```bash
grep -c 'Pending audit' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md   # should be 1
```

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/audits/2026-04-25-backend-architecture-audit.md
git commit -m "$(cat <<'EOF'
docs(audit): §4 — services/email_templates.py (841 lines)

Identifies <N> provider templates plus shared logic conflated, proposes
split into backend/app/services/email_templates/ package.
Effort: <S/M/L/XL>. Tests: <safe/risky/unknown>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Replace placeholders before committing.

---

### Task 6: Audit §5 — `backend/app/services/email_service.py` (782 lines)

**Files:**
- Read: `backend/app/services/email_service.py`
- Search: `backend/tests/` for any `*email_service*` test
- Reference: `graphify-out/GRAPH_REPORT.md`
- Modify: `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md` (replace `_Pending audit._` under §5)

- [ ] **Step 1: Read source**

```
Read backend/app/services/email_service.py
```

This service is likely the "front door" the API/tasks call to interact with mail. Look for: provider abstraction, top-level methods that orchestrate fetching/parsing.

- [ ] **Step 2: Find and read tests**

```bash
ls backend/tests/ | grep -i 'email_service\|email_svc'
find backend -name 'test_email_service*'
```

If no direct test file, mark coverage as `unknown` or `risky` and explain in §Couverture tests.

- [ ] **Step 3: Pull graph data + check overlap with email_templates**

```bash
grep -n 'email_service\|services/email_service' graphify-out/GRAPH_REPORT.md | head -20
```

This file may delegate heavily to `email_templates.py`. If so, surface this as a finding for §A (cross-cutting).

- [ ] **Step 4: Apply the template; Edit §5**

Edit `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md`:

- `old_string`:
  ```
  ## §5 — `backend/app/services/email_service.py` — 782 lines

  _Pending audit._
  ```

- `new_string`: full §5.

If `email_service.py` substantially overlaps with `email_templates.py`, the proposed split may include a merge step (e.g., "merge into the new `email_templates/` package, which already covers the parsing surface area; this file's residual orchestration logic moves to `email_templates/orchestrator.py`"). That's a valid recommendation — surface it.

- [ ] **Step 5: Verify**

```bash
grep -c 'Pending audit' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md   # should be 0
awk '/^## §[1-5] /,/^## §[2-A] /' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md | grep -c '^### '
```

The second command counts `###` sub-section headers across §1-§5. With 5 files × 6 required sub-sections = expect at least 30.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/audits/2026-04-25-backend-architecture-audit.md
git commit -m "$(cat <<'EOF'
docs(audit): §5 — services/email_service.py (782 lines)

Identifies <N> responsibilities, evaluates overlap with email_templates.py,
proposes <split or merge>. Effort: <S/M/L/XL>. Tests: <safe/risky/unknown>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Replace placeholders before committing.

---

### Task 7: Cross-cutting analysis (§A)

**Files:**
- Read: all 5 source files (high-level scan, looking for repeated patterns)
- Read: each populated §1-§5 in the audit doc
- Reference: `graphify-out/GRAPH_REPORT.md` for community/centrality info
- Modify: `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md` (replace `_Pending cross-cutting analysis._` under §A)

- [ ] **Step 1: Scan for repeated patterns across the 5 files**

Run pattern greps on the 5 files. Each pattern that hits 2+ files is a candidate finding:

```bash
files="backend/app/api/subscriptions.py backend/app/tasks/email_sync.py backend/app/api/auth.py backend/app/services/email_templates.py backend/app/services/email_service.py"

# HTML / email parsing
echo "=== BeautifulSoup ==="
grep -l 'BeautifulSoup\|bs4' $files
echo "=== regex parse helpers ==="
grep -l 're\.compile\|re\.search.*email\|re\.match.*\\\\b' $files
echo "=== HTTP clients ==="
grep -l 'httpx\|requests\.\|aiohttp' $files
echo "=== exception patterns ==="
grep -l 'HTTPException' $files
grep -l 'raise.*Error\|raise.*Exception' $files | head
echo "=== logging patterns ==="
grep -l 'logger\.\|logging\.' $files
echo "=== auth/session helpers ==="
grep -l 'get_current_user\|current_user\|verify_token' $files
echo "=== DB session patterns ==="
grep -l 'Depends(get_db)\|Session(' $files
echo "=== JSON / serialization ==="
grep -l 'json\.dumps\|json\.loads\|model_dump\|\.dict()' $files | head
echo "=== datetime patterns ==="
grep -l 'datetime\.now\|datetime\.utcnow\|timezone\.' $files
```

For each hit-pattern, decide:
- Is it a generic standard pattern (e.g., `HTTPException` is normal in FastAPI routes) → not a finding.
- Is it duplicated business logic (e.g., 3 files each have their own HTML email parser) → this is a finding.

- [ ] **Step 2: Cross-layer / circular import check**

```bash
# Does any service import from api/?
echo "=== services importing api/ ==="
grep -n 'from app\.api\|from \.api\|import.*api\.' backend/app/services/*.py | head

# Does any task import from api/?
echo "=== tasks importing api/ ==="
grep -n 'from app\.api\|from \.api\|import.*api\.' backend/app/tasks/*.py | head

# Does any model import from services/tasks/api?
echo "=== models with suspicious imports ==="
grep -nE 'from app\.(services|tasks|api)|from \.\.(services|tasks|api)' backend/app/models/*.py | head

# Circular imports surfaced by graphify
grep -i 'circular\|cycle' graphify-out/GRAPH_REPORT.md | head
```

Each non-empty result is a candidate finding for §A.

- [ ] **Step 3: Doc-vs-code drift check (light)**

For any architecture doc that should reflect what's in these 5 files:

```bash
# Does docs/architecture/auth.md still match api/auth.py reality?
grep -E '^## ' docs/architecture/auth.md
# Vs. what auth.py actually exposes:
grep -E '^@router\.|^async def ' backend/app/api/auth.py | head -30

# Same for email-pipeline:
grep -E '^## ' docs/architecture/email-pipeline.md
```

If the docs claim something the code no longer does (or vice versa), note it for §A. (We will NOT fix it here — out-of-scope.)

- [ ] **Step 4: Read the 5 populated sections to spot patterns surfaced individually**

```
Read docs/superpowers/audits/2026-04-25-backend-architecture-audit.md
```

Scan for: same responsibility named in multiple files? Same dependency flagged in multiple §Couplages?

- [ ] **Step 5: Write §A**

Edit `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md`:

- `old_string`:
  ```
  ## §A — Constats transverses

  _Pending cross-cutting analysis._
  ```

- `new_string`:
  ```
  ## §A — Constats transverses

  Findings that affect 2+ of the audited files. <Brief intro sentence.>

  ### A.1 — <finding title>

  - **Files concernés**: §<N>, §<M>, ...
  - **Constat**: <2-3 sentence description with concrete evidence>
  - **Impact**: <1 sentence on why this matters for the refactor>

  ### A.2 — <finding title>

  ...

  <Repeat for each finding. If no transverse pattern was detected:>

  _No transverse pattern detected — refactors can proceed independently._
  ```

Aim for 2-5 findings. If more than 5 emerge, the scope was too narrow — note this fact at the bottom of §A and flag for §C.

- [ ] **Step 6: Verify**

```bash
grep -c 'Pending cross-cutting' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md   # should be 0
awk '/^## §A /,/^## §B /' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md | grep -c '^### A\.'   # number of findings
```

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/audits/2026-04-25-backend-architecture-audit.md
git commit -m "$(cat <<'EOF'
docs(audit): §A — cross-cutting findings

Identifies <N> patterns affecting 2+ of the audited files (or none).
Surfaces shared duplication / layer violations / circular imports that
inform the priority order in §B.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Replace `<N>` with the actual count before committing.

---

### Task 8: Roadmap priorisée (§B)

**Files:**
- Read: the 5 populated per-file sections + §A
- Modify: `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md` (replace `_Pending prioritisation._` under §B)

- [ ] **Step 1: Re-read the audit so far**

```
Read docs/superpowers/audits/2026-04-25-backend-architecture-audit.md
```

- [ ] **Step 2: Score each refactor**

For each of the 5 files, jot down a quick score on 3 axes (no need to commit this scratchpad):

- **Impact (1-3)**: how much does fixing this improve the codebase? (god-files of 1400 lines = 3; 800 lines = 2)
- **Ease (1-3)**: based on T-shirt size — S=3, M=2, L=2, XL=1
- **Inverse risk (1-3)**: tests safe = 3, risky = 2, unknown = 1

Composite priority = impact + ease + inverse_risk (range 3-9).

Higher composite = earlier in the roadmap. Tie-break by impact, then ease.

If §A surfaced a "split A before B because shared dependency" finding, override the composite ordering accordingly (note the override in the rationale).

- [ ] **Step 3: Group into phases**

Refactors that share dependencies or naturally bundle (e.g., merge `email_service.py` and `email_templates.py` together) go in the same phase. Otherwise, one refactor per phase.

- [ ] **Step 4: Write §B**

Edit `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md`:

- `old_string`:
  ```
  ## §B — Roadmap priorisée

  _Pending prioritisation._
  ```

- `new_string`:
  ```
  ## §B — Roadmap priorisée

  Recommended execution order for sub-project C1, derived from the
  per-file analyses (§1-§5) and cross-cutting findings (§A). Effort
  is the sum of the constituent T-shirt sizes; risk is the worst of
  the constituent risks.

  ### Phase C1.1 — <name>

  - **Files**: §<N>[, §<M>...]
  - **Why first**: <one-sentence rationale, e.g. "biggest impact, lowest risk, no upstream dependencies">
  - **Effort**: <T-shirt sum, e.g. "M+S = M-L">
  - **Risk**: <low/medium/high>
  - **Dependencies**: <_None_, or "blocked by Phase X">

  ### Phase C1.2 — <name>

  ...

  ### Phase C1.N — <name>

  ...

  ### Total estimated effort

  <sum of phase efforts, with a rough hour bracket — e.g. "4 phases summing
  to ~M+L+M+S, roughly 12-25 hours of focused refactor work">.

  ### Caveats

  <Any tradeoff or caveat the orchestrator should know — e.g. "Phase 2
  should land before any Phase 4 work to avoid a merge conflict on
  email_service.py."> If none, write `_None._`.
  ```

Each phase MUST cover at least one of §1-§5. The roadmap collectively MUST cover all 5 files (no audited file is left without a phase).

- [ ] **Step 5: Verify**

```bash
grep -c 'Pending prioritisation' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md   # should be 0

# Each of §1-§5 must be referenced from §B
awk '/^## §B /,/^## §C /' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md > /tmp/audit-B.md
for n in 1 2 3 4 5; do
  grep -c "§$n" /tmp/audit-B.md
done
rm /tmp/audit-B.md
```

Expected: each `§N` referenced at least once in §B.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/audits/2026-04-25-backend-architecture-audit.md
git commit -m "$(cat <<'EOF'
docs(audit): §B — prioritised refactor roadmap for C1

Orders the 5 refactors into <N> phases by impact × ease × inverse-risk,
with explicit dependencies between phases. Total estimated effort:
<bracket>. Becomes the proto-spec for sub-project C1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Replace `<N>` and `<bracket>` before committing.

---

### Task 9: Out-of-scope (§C)

**Files:**
- Read: the full audit doc
- Modify: `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md` (replace `_Pending listing._` under §C)

- [ ] **Step 1: Re-read the full audit**

```
Read docs/superpowers/audits/2026-04-25-backend-architecture-audit.md
```

- [ ] **Step 2: Identify out-of-scope items**

While reading, list everything noticed BUT NOT addressed in §1-§B. Common candidates:

- Files that are big but didn't make the top-5 (e.g., `api/mailboxes.py` at 743 lines, `api/oauth.py` at 547 lines).
- Smells flagged in §A that need their own follow-up (e.g., a circular import not directly tied to the audited 5).
- Doc/code drift identified during cross-cutting (gap between `docs/architecture/*.md` and current code).
- Speculative refactor opportunities that need more investigation before action.

You may also want to surface:

- `docs/architecture/auth.md:99` — known `<!-- duplicates the above; reconcile manually -->` marker from a prior session, still pending.

- [ ] **Step 3: Write §C**

Edit `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md`:

- `old_string`:
  ```
  ## §C — Out-of-scope

  _Pending listing._
  ```

- `new_string`:
  ```
  ## §C — Out-of-scope

  Items noticed during this audit but explicitly NOT addressed in C1. Each
  is captured here for future spec brainstorming.

  ### C.1 — <item title>

  - **Description**: <2 sentences>
  - **Why deferred**: <why this is not part of C1>
  - **Suggested follow-up**: <which sub-project / spec / future audit should pick this up>

  ### C.2 — <item title>

  ...
  ```

Aim for 3-7 items. If none, write `_No out-of-scope items emerged. The 5 audited files capture all near-term refactor priorities._` — but be honest: there is almost always something to surface.

- [ ] **Step 4: Verify**

```bash
grep -c 'Pending listing' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md   # should be 0
grep -c '^### C\.' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md   # count of out-of-scope items
```

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/audits/2026-04-25-backend-architecture-audit.md
git commit -m "$(cat <<'EOF'
docs(audit): §C — out-of-scope items for future sub-projects

Lists <N> items noticed during the C6 audit but not addressed in C1.
Each item points to its suggested follow-up (sub-project / spec / audit).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Replace `<N>` before committing.

---

### Task 10: Final review, push, and PR

**Files:**
- Read: the complete audit doc
- Push: branch `chore/c6-backend-audit`
- Create: GitHub PR

- [ ] **Step 1: Final structural verification**

```bash
test -f docs/superpowers/audits/2026-04-25-backend-architecture-audit.md && echo "doc OK"
wc -l docs/superpowers/audits/2026-04-25-backend-architecture-audit.md

# All 9 sections populated (no Pending placeholders left)
grep -c 'Pending' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md   # should be 0

# All 5 per-file sections have all 6 required sub-headers
for n in 1 2 3 4 5; do
  echo "=== §$n ==="
  awk -v n="$n" 'BEGIN{p=0} /^## §/ {p=($2 == "§"n); next} p {print}' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md | grep -c '^### '
done
```

Expected: each per-file section has at least 6 `### ` sub-headers.

- [ ] **Step 2: Quality bar from spec §8**

```bash
# Every Couplages section cites at least one specific module name (heuristic: contains a backtick `module.py` somewhere)
awk '/^### Couplages/,/^### / {if (/`[a-z_/]+\.py`/) c++} END{print c}' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md

# Every Effort entry has a T-shirt size (S/M/L/XL)
grep -E '\*\*Effort\*\*: (S|M|L|XL)' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md | wc -l   # should be 5

# §A has at least one finding OR explicit no-finding statement
awk '/^## §A /,/^## §B /' docs/superpowers/audits/2026-04-25-backend-architecture-audit.md | grep -cE '^### A\.|No transverse'
```

If any check fails, surface the failure as a status `DONE_WITH_CONCERNS` and continue (do not block on quality bar). The user can review.

- [ ] **Step 3: Commit history check**

```bash
git log --oneline origin/main..HEAD
```

Expected: ~10 commits, each scoped (`docs(audit): §N — ...`).

- [ ] **Step 4: Push the branch**

```bash
git push -u origin chore/c6-backend-audit
```

- [ ] **Step 5: Create the PR**

```bash
gh pr create --title "docs(audit): C6 — backend architecture audit (5 god-files)" --body "$(cat <<'EOF'
## Summary

Targeted architecture audit of the 5 largest backend Python modules (~5,665 LoC total), produced under sub-project C6 of the broader code refactor (C). Output is a single Markdown document at `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md` that becomes the proto-spec for sub-project C1 (god-files split).

Per-file analyses (§1-§5) follow a fixed template (Symptômes / Responsabilités identifiées / Couplages / Couverture tests / Proposition de découpe / Effort & dépendances). Cross-cutting findings, prioritised roadmap, and out-of-scope items are surfaced in §A, §B, §C.

Spec: `docs/superpowers/specs/2026-04-25-c6-backend-architecture-audit-design.md`
Plan: `docs/superpowers/plans/2026-04-25-c6-backend-architecture-audit.md`

No code changes — analytical artefact only.

## Test plan

- [ ] Read the audit top-to-bottom once: does it read coherently?
- [ ] §B roadmap is internally consistent (every per-file section has a phase)
- [ ] Effort sizes look reasonable for the proposed splits
- [ ] §C out-of-scope items make sense as future follow-ups
- [ ] No `_Pending …_` placeholders remain in the document
- [ ] Decide whether to start C1 brainstorming using §B as the proto-spec

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 6: Final report**

Surface a one-line summary:

```
✅ C6 audit complete on branch chore/c6-backend-audit.
   - 10 commits
   - 1 audit doc at docs/superpowers/audits/2026-04-25-backend-architecture-audit.md
   - 5 per-file sections + §A + §B + §C
   - PR opened: <URL from gh pr create output>
   Ready for review. §B is the proto-spec for C1.
```

---

## Self-Review (already performed)

- **Spec coverage**: every section of the spec maps to at least one task. §1-§5 → Tasks 2-6. §A → Task 7. §B → Task 8. §C → Task 9. The "deliverable" requirement (one doc at the specified path) → Task 1 (skeleton) + 8-10 (final). The "fixed template" requirement → quoted inline before Task 2. The "Stop — no implementation" requirement is honoured (Task 10 ends with PR creation, no further work).
- **Placeholder scan**: angle-bracket placeholders (`<N>`, `<S/M/L/XL>`, `<safe/risky/unknown>`, etc.) appear in commit-message and section templates by design — they are EXPLICITLY marked as "to be replaced before commit/edit" in their respective tasks. No literal `TBD` / `TODO` / `fill in details`.
- **Type / name consistency**: file paths, section IDs (§1-§5, §A, §B, §C), branch name (`chore/c6-backend-audit`), audit doc path (`docs/superpowers/audits/2026-04-25-backend-architecture-audit.md`) are spelled identically across every task.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-25-c6-backend-architecture-audit.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`.

Which approach?
