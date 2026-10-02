# CLAUDE.md

## 0. Operating Order

Apply guidance in this order:

1. Direct user request
2. This file
3. `PERSONA.md` — persona, tone, and language
4. `PROJECT.md` — architecture, conventions, and commands
5. Task-specific skills, workflows, or playbooks when the request matches

If instructions conflict, say so briefly and follow the higher-priority source.

At the start of every session, read `PERSONA.md` and `PROJECT.md` before responding.

## 1. Think Before Acting

Don't assume. Surface tradeoffs and ambiguity before proceeding.

- State assumptions when they materially affect the result.
- If multiple interpretations exist, present them instead of choosing silently.
- If something is unclear enough to risk wrong work, stop and ask. "Clear" means only one reasonable interpretation exists; otherwise ask (see §8).
- Treat conclusions as evidence-based. Don't invent requirements, behavior, or design detail.
- For binary files (PDFs, images, Office files): don't infer contents — ask for extracted text or quoted excerpts.

## 2. Minimum Viable Change

Do the least work that solves the problem. Touch only what the task requires.

- No features beyond the request.
- Reuse before writing: follow the ladder in §12.
- No refactoring of unrelated content.
- No reformatting adjacent sections unless the change requires it.
- Match local style, naming, and folder conventions.
- Remove only what your own change made obsolete.

The test: every changed line traces directly to the task.

## 3. Goal-Driven Execution

Define success criteria. Verify before reporting done.

For complex tasks:
- Break into steps with clear verification per step.
- Call out dependencies and decision points that affect success.

Translate requests into checks you can prove:
- Bug fix: reproduce → change → verify.
- New feature: failing test first (confirm it fails) → implement → refactor with tests green.
- New endpoint: schema defined → core logic tested → endpoint tested → every adapter works.
- Refactor: lint and type checks clean → tests green → every adapter still behaves correctly (commands in `PROJECT.md`).
- Diagram: validate syntax before finalizing.

Once a bug fix traces to a reusable pattern (a hook, a shared attribute, a copy-pasted block), grep the codebase for every other place that pattern appears and fix them together in the same change — before reporting done. Same-pattern fixes are in scope for §2. Don't wait for the same bug to be reported page by page.

## 4. Work With This Project

Read `PROJECT.md` for project structure, conventions, and commands before making changes.

- Follow the architecture and layer boundaries defined in `PROJECT.md` — don't cross them.
- Match existing naming, formatting, and language conventions.
- Prefer updating an existing file over creating a parallel one.
- Check for a relevant skill or playbook before proceeding ad hoc.

## 5. Place Work Where It Belongs

Follow the directory layout in `PROJECT.md`. When in doubt:
- Pure logic belongs in the core/domain layer — no I/O, no side effects.
- I/O, formatting, and user interaction belong in adapter layers (as defined in `PROJECT.md`).
- Tests mirror the structure of the code they cover.

Keep drafts and scratch work separate from canonical files unless asked otherwise.

## 6. Reviews And Standards

- Prioritize concrete findings: risks, gaps, inconsistencies, missing decisions.
- Keep summaries brief unless depth is requested.
- Tie findings to the relevant risk or requirement when possible.
- If no checklist exists, say so and review against the most relevant observable expectations.
- For API changes: verify schema, endpoint behaviour, adapter parity, and lint/type cleanliness.

## 7. Diagram Expectations

- Use Mermaid unless asked otherwise.
- Clear titles, concise labels, only necessary notes.
- Validate syntax before finalizing.

## 8. Output Style

Short and direct by default. Expand only when the task is complex or the user asks.

- Prefer conclusions over explanations.
- Avoid filler.
- Act first on clear requests; ask only when the answer would materially change the work.
- After edits: one sentence on what changed and why, nothing more.

## 9. Capture Repeatable Lessons

If the same gap or correction appears more than once in a session:
- Propose the smallest change to shared guidance (this file, `PROJECT.md`, a checklist) that would prevent it next time.
- Don't leave the lesson implicit.

## 10. Architecture Principles

- **Layered architecture** — API/adapters → Service → Domain, no cross-layer shortcuts; Infra implements interfaces the Domain defines (dependency inversion), so the Domain never does I/O itself
- **NFR-first on new designs** — consider: Performance, Availability, Security, Scalability, Observability, Cost
- **Fail fast, observable** — use structured logging and distributed tracing (e.g. OpenTelemetry)

## 11. Hard Constraints (YOU MUST FOLLOW — no exceptions)

- **NEVER commit secrets, API keys, credentials** — use `.env.local` (always gitignored); run a pre-commit secret scan (e.g. gitleaks) where configured
- **NEVER write user personal info (names, emails, health, financial, account data) to any cloud service** — including MCP connectors such as Gmail, Drive, Zapier — local/BYOK only, unless the user explicitly asks for that specific write
- **NEVER run destructive DB commands** (`DROP`, `TRUNCATE`, `DELETE` without WHERE) without explicit confirmation
- **NEVER modify IaC / Terraform files** without explicit instruction
- **NEVER install npm packages globally** without asking first

## 12. Coding Guidelines

- Before writing new code, read what the change touches, then stop at the first step that holds:
  1. Does it need to exist? If not, skip it.
  2. Already in this codebase? Reuse it.
  3. Stdlib or native platform feature? Use it.
  4. Installed dependency? Use it.
  5. Only then: write the minimum that works.
- **NEVER cut validation, error handling, security, or accessibility to stay small.**
- **NEVER weaken lint, type, test, or coverage config to make a check pass.**
