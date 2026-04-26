# C6 — Backend Architecture Audit — Design

**Date**: 2026-04-25
**Status**: Approved (pending user review of this spec file)
**Author**: Brainstorming session — Fabien + Claude
**Sub-project**: C6 (audit) — first sub-project of the broader C decomposition (app code refactor)

## 1. Context & Problem

The doc-refactor + graph sub-project (PR #25, merged) revealed that the backend codebase is significantly larger and more complex than the "Phase 1 MVP" described in the original `TECHNICAL_SPEC.md`. The refreshed graphify analysis (`graphify-out/GRAPH_REPORT.md`) reports:

- 4,143 nodes, 12,220 edges, 201 communities across 302 backend Python files.
- Five files exceed 780 lines, three exceed 1,100 lines:
  - `backend/app/api/subscriptions.py` — 1,441 lines
  - `backend/app/tasks/email_sync.py` — 1,410 lines
  - `backend/app/api/auth.py` — 1,191 lines
  - `backend/app/services/email_templates.py` — 841 lines
  - `backend/app/services/email_service.py` — 782 lines
- Backend has 39 test files (decent baseline); per-file coverage of the god-files is unknown without measurement.

Splitting these god-files is the obvious next refactor, but doing so blindly is risky: every god-file mixes multiple responsibilities, and getting the split wrong creates either dependency cycles or files that grow back to god-status within months. Before touching the code, we need an analytical pass that captures **why** each file is god-y, **where the natural seams are**, and **in what order** to attack them.

This spec describes that analytical pass. It is the first sub-project of the broader C decomposition. Its output is the proto-spec for C1 (backend god-files split).

## 2. Goals & Non-Goals

### Goals

1. **Produce an actionable audit document** for the 5 backend god-files identified above.
2. **Surface cross-cutting findings** (duplication patterns, layer violations, circular imports) that affect more than one of the audited files.
3. **Deliver a prioritised roadmap** that orders future C1 phases by impact × effort × risk, with explicit dependencies between refactors.

### Non-Goals (deferred)

- Implementing any of the proposed refactors (that is C1 onwards).
- Auditing the frontend (deferred until after C3 testing baseline; will become a separate "C6-bis" sub-project with its own graph generation).
- Auditing every backend module exhaustively (that was option (b) in brainstorming, ruled out).
- Updating existing architecture docs (`docs/architecture/*.md`) to reflect current state. If discrepancies surface during the audit, they are noted in the "Cross-cutting findings" section but not fixed in this spec.
- Generating new graph artefacts (the existing `graphify-out/GRAPH_REPORT.md` and per-module `wiki/` are sufficient input).
- Producing precise hour-level effort estimates. The audit uses T-shirt sizes (S / M / L / XL).

## 3. Scope

The audit covers **exactly** these 5 files:

| Rank | File | Lines | Known test file(s) |
|---|---|---|---|
| 1 | `backend/app/api/subscriptions.py` | 1,441 | `backend/tests/test_subscriptions_api.py` |
| 2 | `backend/app/tasks/email_sync.py` | 1,410 | (to be confirmed during audit) |
| 3 | `backend/app/api/auth.py` | 1,191 | `backend/tests/test_auth.py` |
| 4 | `backend/app/services/email_templates.py` | 841 | `backend/tests/test_email_templates.py` |
| 5 | `backend/app/services/email_service.py` | 782 | (to be confirmed during audit) |

Total: ~5,665 lines of source to analyse + their associated tests + their `graphify-out/wiki/` pages where they exist.

If during the audit it becomes evident that one of these files is actually a thin wrapper around another (e.g., `email_service.py` mostly delegates to `email_templates.py`), surface this as a cross-cutting finding but still apply the per-file template to both — the merge decision is downstream (C1).

## 4. Per-File Audit Template

Every audited file is analysed using this exact template. Consistency across the 5 files makes the audit grep-able and comparable.

```markdown
## `<relative path>` — `<line count>` lines

### Symptoms

[Why this file is god-y. Concrete signals: how many distinct responsibilities,
heterogeneity of imports, depth of nesting, presence of section-comment
"chapters", etc. 3-6 sentences max.]

### Responsibilities identified

[Numbered list of "roles" mixed in the file. For each: approximate line range
and one-sentence description.]

1. <role 1> (lines X-Y)
2. <role 2> (lines Y-Z)
3. ...

### Couplings (graph-derived)

- **Inbound imports**: N modules import from this file. List notable / surprising importers.
- **Outbound imports**: this file imports from N modules. Flag any cross-layer imports (e.g., a service importing from `api/`, a model importing from `tasks/`).
- **Centrality**: god-node? hub of which graphify community? high betweenness?

### Test coverage

- Test file(s) found: ...
- Approximate coverage estimate (functions defined vs functions touched in tests, by grep).
- Refactor safety: **safe** (good coverage, deterministic) / **risky** (sparse coverage or heavy I/O) / **unknown** (could not measure).

### Proposed split

```
backend/app/<target dir>/
├── <module-1>.py  (~N lines — responsibility)
├── <module-2>.py  (~N lines — responsibility)
└── ...
```

[2-4 sentence justification of why this split and not another.
Specifically: why these boundaries are stable (won't drift back to god-status).]

### Effort & dependencies

- **Effort**: S / M / L / XL
  - S: < 2h (mechanical extraction, tests already cover)
  - M: 2-6h (some refactor in callers needed)
  - L: 6-16h (multi-file restructure, possibly schema/contract changes)
  - XL: > 16h (architectural shift; reconsider scope)
- **Blockers**: other refactors that must happen first (with reference).
- **Blocks**: other refactors that depend on this one.
- **Risk**: low / medium / high (combines coverage + criticality of the file in production).
```

The template is a **fixed contract**. The auditor does not freelance section names. If a section genuinely doesn't apply (e.g., "Couplings" is empty for a file that imports nothing surprising), the section header still appears with content like `_None observed._`.

## 5. Cross-Cutting Sections

Beyond the 5 per-file analyses, the document contains 3 transverse sections:

### §A — Cross-cutting findings

Patterns and findings that affect 2+ of the audited files. Examples to look for:

- Duplicate parsing logic (e.g., HTML email parsing implemented 3 different ways across the 5 files).
- Cross-layer imports (a router importing from a task; a service importing from a router).
- Circular imports surfaced by graphify.
- Repeated boilerplate that begs for a shared helper.
- Inconsistencies with the architecture docs in `docs/architecture/` (flag only — do not fix here).

Target length: 1 page max. If more than ~5 transverse findings emerge, the audit was too narrow and we should reconsider scope (escalate, do not just write longer).

### §B — Prioritised roadmap

The actionable output. Lists the 5 refactors in recommended execution order, with justification.

Format:

```markdown
### Phase 1 — <name>
- File(s): <one or more from the audited 5>
- Why first: <one-sentence rationale>
- Effort: <T-shirt sum>
- Risk: <low/medium/high>
- Dependencies: <upstream / none>

### Phase 2 — <name>
...
```

Phases can group multiple files if they share a refactor (e.g., merging `email_service.py` into `email_templates.py` plus splitting the result might be one phase).

### §C — Out-of-scope

Things noticed during the audit that are NOT addressed in C1:

- Files that are big but fell outside the top 5 (e.g., `api/mailboxes.py` at 743 lines — close but excluded by the top-5 rule).
- Smells too speculative to act on without further investigation.
- Discrepancies with `docs/architecture/*.md` that need a doc PR rather than a code refactor.

This section ensures the audit does not silently expand scope.

## 6. Methodology / Workflow

The audit is executed in this fixed order:

1. **Per-file pass (5 iterations)**, in the order listed in §3:
   1. Read the file in full.
   2. Read its associated test file(s).
   3. Read its graphify wiki page if present in `graphify-out/wiki/`.
   4. Apply the template from §4. Write that section into the audit document.
   5. Commit (one commit per file, so progress is incremental and reviewable).
2. **Cross-cutting pass**:
   1. With all 5 per-file sections in hand, grep across the 5 files for repeated patterns (literal string heuristics: `BeautifulSoup`, `parse_email`, `httpx.Client`, `HTTPException`, etc.).
   2. Cross-reference graphify community pages relevant to the 5 files.
   3. Write §A.
   4. Commit.
3. **Roadmap pass**:
   1. Order the 5 refactors using the (impact × ease × inverse-risk) heuristic.
   2. Identify natural groupings (e.g., two refactors that should be done together).
   3. Write §B.
   4. Commit.
4. **Out-of-scope pass**:
   1. Re-read the audit. List anything noted but not addressed.
   2. Write §C.
   3. Commit.
5. **Stop.** No further work. The audit is the deliverable.

## 7. Deliverable

A single Markdown document at:

```
docs/superpowers/audits/2026-04-25-backend-architecture-audit.md
```

This requires creating a new directory `docs/superpowers/audits/`, sibling to `specs/` and `plans/`. Convention: audits are dated, treated as snapshots, and may go stale — they are not maintained, they are re-done when needed.

The document follows this top-level structure:

```markdown
# Backend Architecture Audit — 2026-04-25

> Targeted audit of the 5 largest backend Python modules.
> Driven by the C decomposition spec (sub-project C6).

## Method

[Brief: 5 god-files, fixed template, T-shirt sizes, etc. ~10 lines.]

## §1 — `api/subscriptions.py` — 1441 lines
[per-file template]

## §2 — `tasks/email_sync.py` — 1410 lines
[per-file template]

## §3 — `api/auth.py` — 1191 lines
[per-file template]

## §4 — `services/email_templates.py` — 841 lines
[per-file template]

## §5 — `services/email_service.py` — 782 lines
[per-file template]

## §A — Cross-cutting findings

## §B — Prioritised roadmap

## §C — Out-of-scope
```

## 8. Quality Bar

For the audit to be considered complete:

- All 5 files have a fully populated per-file section (no empty sub-sections without an `_N/A_` justification).
- Every "Couplings" sub-section cites at least one specific module name (i.e., it is grounded in actual graph data, not generic prose).
- Every "Proposed split" includes a concrete directory tree with line-count estimates.
- Every "Effort" entry has both a T-shirt size AND a one-sentence justification of why that size.
- §A has at least one finding OR explicitly states "_no transverse pattern detected — refactors can proceed independently_".
- §B presents the 5 refactors in a recommended order with justification.
- §C is non-empty (something always falls outside scope; if not, the scope was wrong).

## 9. Effort & Risks

**Total effort**: 2-3 hours of focused analysis. Reading ~5,665 LoC of code plus tests plus wiki pages plus writing structured notes. The implementation plan will likely break this into 2-3 batches.

**Risks**:

- **Cognitive overload**: reading 5 large files in one session degrades quality of analysis. Mitigation: per-file commits (1 file = 1 commit) so the work can pause/resume cleanly.
- **Premature splitting recommendations**: the audit might propose splits that look clean but break under real refactor (e.g., shared helpers that aren't visible from the file alone). Mitigation: every "Proposed split" is justified in 2-4 sentences and is **explicitly a recommendation, not a decision** — C1 brainstorming will revisit each split before implementation.
- **Test coverage estimation is rough**: grep-based coverage is approximate. Mitigation: surface this honestly in each "Test coverage" sub-section as `safe / risky / unknown` and document the method.

## 10. Out of Scope (deferred sub-projects, for traceability)

- **C1** — Implementation of the splits described in the audit's roadmap.
- **C2** — Frontend god-files split (blocked by C3).
- **C3** — Frontend testing baseline (Vitest + RTL setup).
- **C4** — Types & schemas consolidation.
- **C5** — Service-layer DRY/cleanup (this audit may surface inputs but does not do the refactor).
- **C6-bis** — Frontend architecture audit (after C3, with frontend graph generation).
- Updates to `docs/architecture/*.md` if the audit reveals stale content.

These are tracked here purely so that future spec brainstorming can reference this list rather than rediscovering it.
