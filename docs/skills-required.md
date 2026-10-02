# Skills Required — Audit and Recommendation

- **Skill:** `skills-required`
- **Date run:** 2026-10-01
- **Project:** besu-with-firefly (`PROJECT.md` has no stack table yet, so the stack below comes from `docs/architecture.md` §9 and `docs/plan.md`)

**Confirmed stack:** Python 3.11+ (`ruff`, `mypy`, `pytest`, `httpx`), Solidity compiled with Hardhat (compile only), Hyperledger Besu (QBFT), FireFly, Paladin (Noto), Caliper (Node.js), Docker Compose. No web frontend, no Express, no CI/CD (D-11, D-13).

---

## 1. Prune table

31 project skills were audited from `.claude/skills/`. **Nothing has been deleted.** Deletion needs your explicit Y per skill.

| Skill | Installed path | Assessment | Reason |
|---|---|---|---|
| `architecture` | `.claude/skills/architecture/` | Relevant | Generated `docs/architecture.md` |
| `deliverables` | `.claude/skills/deliverables/` | Relevant | Generated `docs/deliverables.md` |
| `plan` | `.claude/skills/plan/` | Relevant | Generated `docs/plan.md` |
| `prd` | `.claude/skills/prd/` | Relevant | Generated `docs/prd.md` |
| `usecase` | `.claude/skills/usecase/` | Relevant | Generated `docs/use-cases.md` |
| `grill-me` | `.claude/skills/grill-me/` | Relevant | Planning interview |
| `tasks` | `.claude/skills/tasks/` | Relevant | Next step: break the plan into tasks |
| `q` | `.claude/skills/q/` | Relevant | Session context loader |
| `skills-required` | `.claude/skills/skills-required/` | Relevant | This audit |
| `design-doc-mermaid` | `.claude/skills/design-doc-mermaid/` | Relevant | Mermaid diagrams are the project standard |
| `full-output-enforcement` | `.claude/skills/full-output-enforcement/` | Relevant | Needed for long contract and config output |
| `pr-review` | `.claude/skills/pr-review/` | Relevant | General review of changes |
| `github-actions-templates` | `.claude/skills/github-actions-templates/` | Borderline | D-11 says no CI/CD for now, but a later `ruff`/`mypy`/`pytest` workflow is plausible |
| `playwright-e2e` | `.claude/skills/playwright-e2e/` | Borderline | No web frontend and no Playwright (D-13), but it would apply if a web adapter is added later |
| `agent-browser` | `.claude/skills/agent-browser/` | Borderline | Could check the FireFly Explorer UI by hand, otherwise unused |
| `express-production` | `.claude/skills/express-production/` | Irrelevant | Express/Node API patterns; this project has no Express service (the Node part is Caliper only) |
| `brandkit` | `.claude/skills/brandkit/` | Irrelevant | Brand-guideline image generation; no UI or branding in scope |
| `design-taste-frontend` | `.claude/skills/design-taste-frontend/` | Irrelevant | Frontend design; no frontend |
| `design-taste-frontend-v1` | `.claude/skills/design-taste-frontend-v1/` | Irrelevant | Frontend design; no frontend |
| `emil-design-eng` | `.claude/skills/emil-design-eng/` | Irrelevant | UI polish; no UI |
| `gpt-taste` | `.claude/skills/gpt-taste/` | Irrelevant | Landing-page and motion design; no UI |
| `high-end-visual-design` | `.claude/skills/high-end-visual-design/` | Irrelevant | Visual design; no UI |
| `image-to-code` | `.claude/skills/image-to-code/` | Irrelevant | Image-to-website; no UI |
| `imagegen-frontend-mobile` | `.claude/skills/imagegen-frontend-mobile/` | Irrelevant | Mobile screen concepts; no mobile app |
| `imagegen-frontend-web` | `.claude/skills/imagegen-frontend-web/` | Irrelevant | Website design images; no website |
| `impeccable` | `.claude/skills/impeccable/` | Irrelevant | Frontend UX review; no frontend |
| `industrial-brutalist-ui` | `.claude/skills/industrial-brutalist-ui/` | Irrelevant | UI style; no UI |
| `minimalist-ui` | `.claude/skills/minimalist-ui/` | Irrelevant | UI style; no UI |
| `redesign-existing-projects` | `.claude/skills/redesign-existing-projects/` | Irrelevant | Website redesign; no website |
| `stitch-design-taste` | `.claude/skills/stitch-design-taste/` | Irrelevant | DESIGN.md for Google Stitch; no UI |
| `ui-ux-pro-max` | `.claude/skills/ui-ux-pro-max/` | Irrelevant | UI/UX design intelligence; no UI |

**Proposed deletions (16 irrelevant skills), pending your reply:** `express-production`, `brandkit`, `design-taste-frontend`, `design-taste-frontend-v1`, `emil-design-eng`, `gpt-taste`, `high-end-visual-design`, `image-to-code`, `imagegen-frontend-mobile`, `imagegen-frontend-web`, `impeccable`, `industrial-brutalist-ui`, `minimalist-ui`, `redesign-existing-projects`, `stitch-design-taste`, `ui-ux-pro-max`. Fifteen are UI, design or image-generation skills, and one is `express-production`. The three borderline skills are kept.

Note: `.claude/skills/` is shared with other projects the user may work on. Check that nothing else depends on the design skills before deleting.

---

## 2. Suggestion table

Already available and therefore **not** suggested: `python-testing-patterns`, `python-design-patterns`, `pytest-coverage`, `bash-scripting`, `security-review`, `typescript-advanced-types`, `github-actions-templates`, `design-doc-mermaid`, `pr-review`.

Registry searches (`npx skills find`) covered Solidity, Hardhat, Ethereum, Docker Compose, Python CLI and pytest, Besu, FireFly, Paladin and Caliper. **No skill exists for FireFly, Paladin, Caliper or Besu.** The results for those queries were unrelated. The FireFly, Paladin and Caliper knowledge has to come from their own documentation and the Phase 0 spike.

| Priority | Skill | Why this project needs it | Install command |
|---|---|---|---|
| High | `wshobson/agents@solidity-security` (14.8K installs) | Phase 2 deploys the official T-REX suite; reviews contract security patterns | `npx skills add wshobson/agents@solidity-security` |
| High | `wshobson/agents@web3-testing` (10.3K installs) | Hardhat and contract test patterns for the compile and compliance-rejection tests | `npx skills add wshobson/agents@web3-testing` |
| Medium | `affaan-m/ecc@docker-patterns` (12.6K installs) | About 15 containers in one Compose stack (Phase 1 to 3) | `npx skills add affaan-m/ecc@docker-patterns` |
| Medium | `nomicfoundation/hardhat-skills@hardhat` (105 installs) | Official Hardhat vendor, but a low install count; check the source repo before relying on it | `npx skills add nomicfoundation/hardhat-skills@hardhat` |
| Low | `mindrally/skills@ethereum` (720 installs) | General Ethereum background; the project has no direct Ethereum app code | `npx skills add mindrally/skills@ethereum` |
| Not suggested | `jamie-bitflight/claude_skills@python3-development` (43 installs) | Python testing and design are already covered by `python-testing-patterns`, `python-design-patterns` and `pytest-coverage`; low install count | n/a |

Quality notes: install counts are from the registry listing; the source repositories were not inspected. Review a skill's source before installing it.

---

## 3. Actions taken (2026-10-01, on the user's instruction "do all")

- **Removed 16 skills** with `npx skills remove ... -y` from the repo root: `express-production`, `brandkit`, `design-taste-frontend`, `design-taste-frontend-v1`, `emil-design-eng`, `gpt-taste`, `high-end-visual-design`, `image-to-code`, `imagegen-frontend-mobile`, `imagegen-frontend-web`, `impeccable`, `industrial-brutalist-ui`, `minimalist-ui`, `redesign-existing-projects`, `stitch-design-taste`, `ui-ux-pro-max`. They are gone from `.claude/skills/`, `.agents/skills/` and `skills-lock.json`. The CLI reported 14 removed because `express-production` was never in its store and one other had already been deleted by hand earlier.
- **Installed 2 skills into this repo (project scope, not global):** `wshobson/agents@solidity-security` and `wshobson/agents@web3-testing`, via `npx skills add wshobson/agents -s solidity-security -s web3-testing -y`. Files are in `.agents/skills/`, linked at `.claude/skills/`, and recorded in `skills-lock.json`. The registry's security scan showed both as Safe (Socket 0 alerts, Snyk Low Risk).
- **Cleanup:** a first install attempt ran from the wrong directory and left stray `.claude/skills/.agents/`, `.claude/skills/.claude/` and `.claude/skills/skills-lock.json`. These were deleted and the install was rerun from the repo root.
- **Installed 2 more on the user's follow-up ("install medium and low if they are safe"):** `nomicfoundation/hardhat-skills@hardhat` and `mindrally/skills@ethereum`. The CLI scan showed both Safe (0 alerts, Low Risk), and skills.sh showed Gen, Socket and Snyk all passing. Caveat: the `hardhat` skill targets Hardhat 3, so check the Hardhat version chosen in Phase 0 before relying on it.
- **Not installed:** `affaan-m/ecc@docker-patterns` (4.6K installs). skills.sh lists **Snyk: Fail** for it (Gen and Socket pass), so it was skipped under the "only if safe" condition. Revisit if the audit changes.
- **`ethereum` replaced (2026-10-02, on the user's instruction).** The registry version (`mindrally/skills@ethereum`) was removed with `npx skills remove ethereum -y`, and the user's own version was written to `.claude/skills/ethereum/SKILL.md`. It is now an authored project skill, so it is no longer in `skills-lock.json` and `npx skills update` will not touch it. The closing reference to a `dlt-security-review` skill (not installed here, and not in the registry) was removed on the user's instruction. The text still names `GPT-5.4` as the preferred model; that is left as supplied.
- The install and remove rules are now written into `.claude/skills/skills-required/SKILL.md` so a future run follows the same project-local procedure.

**Skills now in `.claude/skills/` (19):** 15 authored or kept project skills (`agent-browser`, `architecture`, `deliverables`, `design-doc-mermaid`, `full-output-enforcement`, `github-actions-templates`, `grill-me`, `plan`, `playwright-e2e`, `pr-review`, `prd`, `q`, `skills-required`, `tasks`, `usecase`) plus `solidity-security`, `web3-testing`, `hardhat` and `ethereum`. Also in `.agents/skills/` but not linked in `.claude/skills/`: `claude-api`, `install-skill`, `security-review`, `skill-creator`.

---

## 4. Summary

31 project skills were audited. With the user's approval, the 16 irrelevant ones (15 UI, design or image-generation skills plus `express-production`) were removed; 3 borderline skills were kept and 12 were relevant. Five new skills were suggested (2 High, 2 Medium, 1 Low) and 4 are now installed in this repo: the 2 High-fit ones (`solidity-security`, `web3-testing`) plus `hardhat` and `ethereum`. `docker-patterns` was skipped because Snyk lists a Fail for it. Python, Mermaid, review and shell coverage was already in place. The remaining gap is FireFly, Paladin, Caliper and Besu, where **no registry skill exists**, so the Phase 0 spike and the official docs must fill it.
