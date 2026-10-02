---

name: ethereum

description: Use for Ethereum and Solidity work including smart contract design, implementation, review, testing, OpenZeppelin integration, Hardhat-based development, gas and storage optimization, and secure transaction-handling patterns. Trigger when asked to write or explain Solidity contracts, ERC token logic, upgradeable contracts, contract tests, or Ethereum backend integration.

user-invocable: true

---

# Ethereum Development


## When to Use

- Write or modify Solidity smart contracts.

- Design ERC-20, ERC-721, ERC-1155, permit, votes, snapshot, custody, or admin-controlled token logic.

- Add OpenZeppelin-based access control, pausing, timelocks, token safety, or upgradeability.

- Create or review Hardhat tests, deployment scripts, and contract integration code.

- Explain Solidity patterns, EVM behavior, storage layout, gas costs, or contract security tradeoffs.

- Review backend code that interacts with Ethereum contracts, wallets, or transaction submission paths.

## When Not to Use

- Do not use this for non-Ethereum blockchain stacks unless the user only wants transferable high-level principles.

- Do not assume upgradeability, governance, or token standards unless the user or code actually needs them.

- Do not recommend added complexity such as proxies, assembly, or custom cryptography unless a real requirement justifies it.

- When the task is primarily contract hardening, audit preparation, or contract-level security review, prefer `solidity-security`.

## Core Approach

- Keep answers direct and implementation-focused.

- Prefer secure defaults over clever patterns.

- Flag uncertainty explicitly when chain, compiler version, token standard, or operational assumptions are missing.

- Favor battle-tested libraries and patterns before custom implementations.

- Keep generated code internally consistent with the project's existing toolchain and style.

## Development Principles

### Solidity design

- Use explicit visibility and mutability on every function.

- Use NatSpec for public and external interfaces and for security-sensitive or admin-sensitive flows when it materially improves reviewability.

- Use `I`-prefixed PascalCase names for interfaces.

- Prefer custom errors over revert strings for frequently hit paths.

- Use events for meaningful state changes and admin actions.

- Keep state transitions easy to reason about; avoid hidden side effects.

- Apply Checks-Effects-Interactions when external calls are involved.

- Prefer pull-based withdrawals over push-based payments when funds distribution is involved.

- Use modifiers sparingly and only when they improve clarity.

### Access control and governance

- Start with the simplest acceptable model: `Ownable` when one admin is enough, `AccessControl` when roles are genuinely distinct.

- If admin power is sensitive, consider `Pausable`, `TimelockController`, or multi-step admin flows.

- Make centralized powers explicit in code and explanation.

- Confirm permissions inside the contract, not only in off-chain services.

### OpenZeppelin usage

- Prefer OpenZeppelin implementations for standard token behavior and common guardrails.

- Use `SafeERC20` for token interactions.

- Use `ReentrancyGuard` when external call patterns make reentrancy risk non-trivial.

- Use `Address` utilities only when they materially improve safety or readability.

- For upgradeable systems, use the upgradeable OpenZeppelin variants consistently and preserve storage layout discipline.

### Optimization discipline

- Optimize only after correctness and security are clear.

- Use Solidity `>=0.8.x` checked arithmetic unless `unchecked` has a measured reason.

- Prefer storage packing, `immutable`, and reduced state writes before lower-level tricks.

- Use inline assembly only for a justified hot path and explain the safety assumptions.

## Testing Expectations

- Cover happy path, authorization failure, input validation, state-transition edges, and revert paths.

- Add integration tests for multi-contract interactions.

- For token or financial logic, include edge cases around balances, allowances, rounding, and replay-sensitive flows.

- Where appropriate, suggest property-based or invariant-style testing.

- Use static analysis and audit-oriented review for high-risk contracts when those tools are available.

- Prefer concrete tools such as Slither and Mythril when they fit the local workflow and are available in the environment.

## Hardhat Workflow

When the repository uses Hardhat, prefer this workflow:

1. Read the target contract, tests, and config before changing code.

2. Identify the minimal safe contract or test change.

3. Implement contract changes with explicit security reasoning.

4. Add or update Hardhat tests for the changed behavior.

5. Run the narrowest relevant test or compile check first.

6. If deployment scripts are touched, verify constructor or initializer arguments and network-specific config.

7. If the repository already has lint, format, coverage, or pre-commit hooks, keep changes compatible with that pipeline instead of introducing a parallel workflow.

If the repo uses another toolchain such as Foundry, adapt to the local toolchain instead of forcing Hardhat.

## Security Review Heuristics

Always check these areas when reviewing or writing Solidity code:

- Reentrancy and external call ordering.

- Access control on every state-changing external surface.

- Upgradeability safety and storage layout discipline when proxies are used.

- Unsafe assumptions about `msg.sender`, `tx.origin`, signatures, or calldata.

- Unbounded loops over attacker-growable state.

- Missing pause, circuit-breaker, or emergency-response paths where funds or permissions are sensitive.

- Event coverage for actions that operations, audit, or off-chain systems depend on.

- Backend transaction submission logic for nonce races, signer reuse, or chain ID assumptions when relevant.

## Procedure

1. Determine whether the task is implementation, explanation, review, testing, or integration.

2. Read the local contracts, tests, and toolchain config before proposing structure.

3. Identify the token standard, access model, upgrade model, and trust boundaries actually in scope.

4. Choose the simplest correct OpenZeppelin or native Solidity pattern that satisfies the need.

5. Implement or explain the change with security and operational consequences made explicit.

6. Add or update tests for the affected path.

7. Validate with the narrowest available compile or test command.

## Output Rules

- Prefer code and concrete implementation guidance over abstract theory.

- Keep explanations concise, but include tradeoffs when they affect safety or maintainability.

- When giving code, make it runnable within the project's existing setup whenever possible.

- If a recommendation is speculative, say so explicitly.

- If the request is a review, lead with concrete findings, risks, and missing tests.

## Example Prompts

- `/ethereum implement an ERC20 with permit and role-based minting`

- `/ethereum review this Solidity contract for access control and reentrancy issues`

- `/ethereum write Hardhat tests for this vesting contract`

- `/ethereum explain whether this upgradeable storage layout is safe`

- `/ethereum add Pausable and TimelockController to this admin token flow`

If the task becomes mostly contract-level hardening or audit preparation, switch to `solidity-security`.

## Quality Bar

- Solutions are secure by default and avoid unnecessary novelty.

- Contract code, tests, and deployment assumptions stay aligned.

- Explanations distinguish protocol facts from project-specific assumptions.

- Recommendations are grounded in actual Ethereum development practice, not generic web advice.
