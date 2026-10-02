---
name: tasks
description: Break a PRD, spec, or large request into small vertical tasks with acceptance criteria, dependencies, and checkpoints in tasks/todo.md. Invoke after /prd or /plan, or when a task feels too large or vague to start. Read-only — writes no code.
---

# Task Breakdown

Turn a PRD or spec into an ordered list of small, verifiable tasks. `docs/plan.md` answers *which phases and why*; this answers *what to build next, in what order, and how to prove each piece works*.

**Important:** Do NOT write code. The only output is `tasks/todo.md`.

**Skip this skill** for single-file changes with obvious scope, or when the PRD already contains well-defined tasks.

---

## Step 0: Load Context

1. Read the PRD (`docs/prd.md`) or the spec the user points to.
2. Read `CLAUDE.md`, `PROJECT.md`, and `docs/architecture.md` / `docs/plan.md` if they exist.
3. Read the codebase sections the work touches. Note existing patterns and layer boundaries.
4. Read any existing `tasks/todo.md`. If it still has unchecked tasks:
   - Same work being revised → update in place.
   - Different work → **stop and ask.** Never delete, overwrite, or rename it — the tasks may be mid-build in another session.
5. Never invent requirements. Every task traces to a PRD story/FR or the user's request.

---

## Step 1: Map Dependencies

List what depends on what. Build bottom-up: foundations first, following the layer order (Domain → Service → API; I/O in adapters).

Put high-risk or unknown tasks early so they fail fast.

---

## Step 2: Slice Vertically

One task = one complete path through the layers, not one layer.

```
Bad:  Task 1: all schemas · Task 2: all endpoints · Task 3: all UI · Task 4: wire together
Good: Task 1: user can register (schema + logic + endpoint + UI)
      Task 2: user can log in (schema + logic + endpoint + UI)
```

Each slice must leave the system working and testable.

---

## Step 3: Write Tasks

```markdown
## Task N: [Short title]

**Description:** One paragraph.

**Acceptance criteria:**
- [ ] [Specific, testable condition]

**Verification:**
- [ ] Tests pass: [focused test command]
- [ ] Checks clean: [lint / type / build command]
- [ ] *(web UI tasks)* `npx playwright test tests/e2e/<flow>.spec.ts` exits 0

**Dependencies:** [Task numbers, or "None"]

**Files likely touched:**
- `path/to/file`

**Size:** XS | S | M | L
```

Take verification commands from `PROJECT.md`. If none are defined, write `TBD — no command in PROJECT.md` and add it to Open Questions. Do not guess commands.

### Sizing

| Size | Files | Example |
|---|---|---|
| XS | 1 | Add a validation rule |
| S | 1–2 | One endpoint or component |
| M | 3–5 | One feature slice |
| L | 5–8 | Multi-component feature |
| XL | 8+ | **Too large — split it** |

Split a task further if any of these hold:
- More than one focused session of work
- Cannot state acceptance criteria in 3 bullets or fewer
- Touches two or more independent subsystems
- "and" appears in the title

---

## Step 4: Order and Checkpoint

1. Dependencies satisfied before dependents.
2. Every task leaves the system in a working state.
3. A checkpoint after every 2–3 tasks:

```markdown
## Checkpoint: After Tasks 1–3
- [ ] All tests pass
- [ ] Build, lint, and type checks clean
- [ ] Core flow works end-to-end
- [ ] Human review before proceeding
```

---

## Output

- **File:** `tasks/todo.md` (create `tasks/` if missing)
- **Structure:** one-paragraph overview → tasks grouped by phase, with checkpoints between → Open Questions (each with an owner)
- After saving, report: any task sized L or above, unresolved Open Questions, and any `TBD` verification commands.
- Wait for the user to approve the task list before any implementation starts.

---

## Checklist

- [ ] Every task has acceptance criteria and a verification step
- [ ] Dependencies identified and ordered correctly
- [ ] Slices are vertical; no task is XL
- [ ] Checkpoints exist between phases
- [ ] No existing incomplete `tasks/todo.md` was overwritten
- [ ] User has approved the list
