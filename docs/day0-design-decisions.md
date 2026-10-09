# Day 0 design decisions for a production build

Questions to answer **before** building a production system on the pattern this repository demonstrates (Besu, FireFly, ERC-3643 `COIN`, Paladin Noto). Each row is one decision: what to ask, what it covers, why it matters, and what this demo does today so you can see how far it is from production.

**How to use it.** Go through the sections in order: earlier answers settle later ones (for example, section A decides whether section D exists at all). Record each answer, the owner and the date in a decision log. A row marked **Gate** can stop or reshape the project; settle those first.

**Scope values:** Use case · Business · Legal · Network · Token · Privacy · Identity · Integration · Security · Operations · Performance · Delivery.

**Contents:** [A. Use case and business](#a-use-case-and-business) · [B. Legal and compliance](#b-legal-and-compliance) · [C. Network and consensus](#c-network-and-consensus) · [D. Data privacy and Paladin](#d-data-privacy-and-paladin) · [E. Token and smart contracts](#e-token-and-smart-contracts) · [F. Identity and compliance on chain](#f-identity-and-compliance-on-chain) · [G. Integration and FireFly](#g-integration-and-firefly) · [H. Keys and security](#h-keys-and-security) · [I. Operations](#i-operations) · [J. Performance and scale](#j-performance-and-scale) · [K. Delivery and governance](#k-delivery-and-governance)

---

## A. Use case and business

| # | Question | Scope | Rationale | Demo today |
|---|---|---|---|---|
| A1 | What business problem does the chain solve that a shared database or API could not? **Gate** | Use case | If there is no multi-party trust, shared-write or audit need, a blockchain adds cost without benefit. Everything below assumes the answer is a real one. | A teaching demo: no business problem. |
| A2 | Which parties take part, and are they separate legal entities? | Use case | Decides who runs nodes, who holds keys, who is liable, and whether privacy between parties matters. | Three demo identities (Anson, Beatrice, admin) on one machine. |
| A3 | What asset or record is on chain (tokenised fund, bond, deposit, payment, document hash, provenance)? | Use case | Determines the token standard, the privacy model and the regulatory treatment. | A permissioned security token (`COIN`, ERC-3643). |
| A4 | Who issues and who holds? One issuer and many holders, or peers? | Use case | Fits Noto (one notary) or ERC-3643 (one issuer, verified holders) versus Zeto or Pente for peer-to-peer. | One issuer (admin), investors hold. |
| A5 | What is the system of record: the chain, or your existing ledger with the chain as a mirror? **Gate** | Use case | Decides reconciliation, what happens when they disagree, and how much of the business logic lives in contracts. | The chain is the record; there is no other ledger. |
| A6 | What lifecycle events must be supported (issue, transfer, redeem, freeze, corporate actions, recovery)? | Use case | Each event is a contract function or a workflow; missing ones are expensive to add after launch. | Mint, transfer, burn, pause, identity registration. |
| A7 | What are the success measures (volume, latency, cost per transaction, number of parties)? | Business | Turns later performance and sizing questions into numbers. | None; the benchmark is descriptive. |
| A8 | Is this a pilot, a limited launch or full production? What is the exit plan if it is stopped? | Business | A pilot can accept demo-grade shortcuts that production cannot; an exit plan decides how data is retained and migrated. | Demo. |
| A9 | Who owns the platform after launch (business, technology, a consortium)? | Business | Without an owner, upgrades, incidents and member changes have no decision-maker. | The repository owner. |

## B. Legal and compliance

| # | Question | Scope | Rationale | Demo today |
|---|---|---|---|---|
| B1 | What is the legal status of an on-chain record: is a token the asset, or a representation of it? **Gate** | Legal | Decides finality, enforceability and what a court would treat as the record. | Not addressed. |
| B2 | Which jurisdictions and regulators apply (securities, banking, payments, privacy)? | Legal | Fixes the compliance rules the contracts and the operating model must encode. | Not addressed. |
| B3 | Is a data-protection law in scope (GDPR, PIPEDA, local equivalents)? Is a right to erasure required? **Gate** | Legal | Personal data on an immutable chain cannot be deleted. It must stay off chain (or only as hashes with care), which pushes toward Paladin or off-chain storage. | No personal data on chain; wallet addresses only. |
| B4 | Are KYC, AML and sanctions checks required, and who performs them? | Legal | Decides the identity model (section F) and the claim issuers. | A demo claim issuer signs a KYC claim for each wallet. |
| B5 | Is a regulator or auditor given read access, and to what? | Legal | A privacy design must allow a controlled view; this can force the notary or a viewer role. | Notary sees all Noto transactions; `COIN` is public. |
| B6 | What are the record-retention and audit requirements? | Legal | Sets how long state, logs and backups are kept and where. | Not addressed. |
| B7 | Does the institution's third-party, cloud and open-source policy allow this stack (licences, support, vendor risk)? | Legal | Besu, FireFly, Paladin, T-REX and Caliper are open source with their own licences and support models. | Pinned versions; no support contract. |
| B8 | Is there a cross-border data-residency requirement for node data? | Legal | Decides where nodes and databases may run. | One machine. |

## C. Network and consensus

| # | Question | Scope | Rationale | Demo today |
|---|---|---|---|---|
| C1 | Public chain, public permissioned, or private permissioned network? **Gate** | Network | The biggest architectural fork: who may read, write and validate, and who is trusted. | Private permissioned Besu. |
| C2 | Who runs validators, and how many? | Network | Sets decentralisation and fault tolerance. QBFT tolerates fewer than one third faulty validators (4 validators tolerate 1). | 1 validator. |
| C3 | Which consensus: QBFT, IBFT 2.0, Clique, or a public-chain mechanism? | Network | Decides finality (QBFT: immediate), validator management and throughput. | QBFT. |
| C4 | What block period and gas limit? | Network | The block period is a floor on confirmed-transaction latency; the gas limit caps block capacity. | 2 s blocks, a very large gas limit, gas price 0. |
| C5 | Is gas priced? Who pays? | Network | A free-gas private network needs another spam control (permissioning); a priced one needs funded accounts. | Gas price 0. |
| C6 | How are nodes admitted and removed (static list, on-chain permissioning, governance vote)? | Network | Decides how a new member joins and how a bad one is removed, and who decides. | `static-nodes.json`. |
| C7 | How are validators added or rotated, and what is the governance of that vote? | Network | A validator change is a consensus change; it needs a process and a quorum rule. | Fixed at genesis. |
| C8 | Which hardware, regions and cloud or on-premises placement for nodes? | Network | Drives latency, resilience and who can see the infrastructure. | Docker on one laptop. |
| C9 | Is the network connected to anything else (public chain, other consortia, bridges)? | Network | Bridges are a major attack surface; most designs should start without. | None. |
| C10 | How are Besu upgrades and hard forks coordinated across organisations? | Network | Members on different versions can split the network. | Single operator, pinned version. |
| C11 | What is the genesis ceremony and who holds the genesis file and validator keys? | Network | Genesis defines chain ID, validators and consensus; it cannot be changed casually. | Generated by `init`, committed (demo only). |

## D. Data privacy and Paladin

| # | Question | Scope | Rationale | Demo today |
|---|---|---|---|---|
| D1 | Is data privacy required for on-chain data in this use case? **Gate** | Use case | It determines whether Paladin (or another privacy layer) is required. If everyone who can read the chain may see every balance and transfer, a plain ERC-3643 token is simpler. | `COIN` public; Noto private, side by side. |
| D2 | What must be hidden: amounts, parties, the fact a transaction happened, or the contract logic? | Privacy | Noto and Zeto hide amounts and parties but not that a transaction occurred; Pente also hides logic. | Noto hides amounts and addresses, not existence. |
| D3 | Hidden from whom: other participants, the node operators, the public, the regulator? | Privacy | Defines the threat model and whether a notary or a group is acceptable. | Hidden from non-parties; the notary sees all. |
| D4 | Who may be the notary, and is one party seeing every transaction acceptable? | Privacy | Noto's model needs a notary that sees all and approves all; if that is unacceptable, use Zeto or Pente. | `notary@node1`, `basic` mode. |
| D5 | Which Paladin domain: Noto, Zeto, Pente, or a mix? | Privacy | Noto: issuer-controlled tokens. Zeto: no one has to be trusted, proofs per transaction. Pente: private smart contracts. | Noto only. |
| D6 | Does a private token need rules (limits, whitelists, approvals)? If so, how are they expressed? | Privacy | Noto `basic` has fixed rules; `hooks` mode needs a Pente contract. Compliance rules that `COIN` enforces on chain have no automatic equivalent. | `basic` mode, no extra rules. |
| D7 | Must private and public assets interoperate (atomic swap, delivery versus payment)? | Privacy | Needs a defined mechanism between Paladin and on-chain contracts; this is non-trivial. | None; the two are independent. |
| D8 | Who runs a Paladin node, and for which organisations? | Privacy | Each party's private data lives on its own node; running someone else's node means they can see it. | Three nodes, one host. |
| D9 | How is private state backed up, and what if a node's database is lost? | Privacy | The chain cannot rebuild private state; losing a node database loses that party's coins and history. | Postgres on a volume; `reset` wipes it. |
| D10 | How are Paladin nodes connected (transport, certificates, mutual TLS, network path)? | Privacy | Node-to-node traffic carries private data; certificate lifecycle and routing are operational duties. | gRPC with mutual TLS, self-signed demo certificates. |
| D11 | Is a zero-knowledge circuit, trusted setup or proving cost acceptable (Zeto)? | Privacy | Proof generation adds latency and compute per transaction. | Not used. |
| D12 | How will privacy be tested and evidenced for audit? | Privacy | You need repeatable proof that the chain shows no amounts or addresses. | `test_the_public_chain_shows_no_amounts_and_no_party_addresses`. |

## E. Token and smart contracts

| # | Question | Scope | Rationale | Demo today |
|---|---|---|---|---|
| E1 | Which token standard: ERC-20, ERC-3643 (T-REX), ERC-1400, ERC-721/1155, or custom? | Token | Fixes the interface, the compliance model and what wallets and tools support. | ERC-3643 (T-REX). |
| E2 | Fungible, non-fungible, or both? Decimals? | Token | Decides the standard and amount handling. | Fungible, 18 decimals. |
| E3 | Is supply capped, and who may mint and burn? | Token | A mint function is the largest power in the system; its holder and limits are a governance decision. | Admin can mint and burn. |
| E4 | Which administrative powers exist (pause, freeze, forced transfer, recovery) and who holds them? | Token | These are needed by regulation and are also a key risk; define the signers and the approval process. | Admin can pause. |
| E5 | Are contracts upgradeable (proxy) or immutable? Who can upgrade and with what approval? | Token | Upgradeability fixes bugs and also adds a trust point; immutability needs a migration plan. | Not upgradeable by design here. |
| E6 | Are the contracts audited, and by whom? What is the process for each change? **Gate** | Token | Contract bugs are permanent and costly; production needs an independent audit and a change control path. | Third-party T-REX artifacts, pinned; not audited by this project. |
| E7 | Which compiler, libraries and contract versions are pinned, and how are they verified? | Token | Reproducible, verifiable bytecode is part of audit and supply-chain control. | Pinned packages in `contracts/`, checksums for Paladin artifacts. |
| E8 | What happens to the token on a chain restart, migration or network exit? | Token | Defines recovery and the ownership of state in a failure or wind-down. | `reset` destroys the chain. |
| E9 | Is the contract set deployed by a repeatable, reviewed procedure? | Token | Deployment is a controlled change; one-off scripts are a risk. | `stack.py deploy`, idempotent. |

## F. Identity and compliance on chain

| # | Question | Scope | Rationale | Demo today |
|---|---|---|---|---|
| F1 | Who may hold the asset, and how is eligibility proven (KYC claim, accreditation, jurisdiction)? | Identity | Defines the identity registry data and the claim topics the token requires. | OnchainID plus a KYC claim per wallet. |
| F2 | Who are the claim issuers, and who trusts them? | Identity | The trusted-issuer list is the root of eligibility; its governance matters as much as the token. | One demo claim issuer. |
| F3 | Which transfer rules apply (country, holder count, limits, lock-ups)? | Identity | They are compliance modules on the token; each rule needs an owner and a change process. | Identity check only. |
| F4 | How are claims revoked or expired, and what happens to a holder who loses eligibility? | Identity | Needs freeze or forced-transfer procedures and a legal basis for them. | Not addressed. |
| F5 | Is any personal data stored in a claim or identity contract? | Identity | On-chain claims should hold proofs, not data; stored data cannot be removed (see B3). | Demo claim only. |
| F6 | How does an existing customer or onboarding system feed the identity registry? | Identity | Eligibility must be synchronised with the source of truth for KYC. | Scripted `onboard`. |

## G. Integration and FireFly

| # | Question | Scope | Rationale | Demo today |
|---|---|---|---|---|
| G1 | Is FireFly needed? Which capabilities: contract API, event listeners, tokens, messaging, data exchange, multiparty? | Integration | FireFly is optional middleware; use only what the use case needs. | Contract API and Explorer. |
| G2 | Which FireFly mode: a single node, or multiparty with each organisation running its own? | Integration | Multiparty adds off-chain messaging and shared state but needs a node per party. | One FireFly node. |
| G3 | What are the upstream and downstream systems (core banking, portfolio, reporting) and how do they connect? | Integration | Defines APIs, events, retry and reconciliation. | CLI and Explorer only. |
| G4 | How are transactions made idempotent and how are failures retried? | Integration | A retried payment must not execute twice. | Idempotency keys exist in the API; not designed end to end. |
| G5 | How are chain events consumed (listeners, webhooks, message bus), and what if a consumer is down? | Integration | Needs ordering, replay and a dead-letter path. | Not built. |
| G6 | How are reorgs and finality treated? | Integration | QBFT has immediate finality, but a system that follows a public chain needs a confirmation policy. | One confirmation block in the benchmark. |
| G7 | Who authenticates users and applications to the API (SSO, mTLS, API keys, roles)? | Integration | The demo API has no authentication. | None. |
| G8 | What are the API contracts and versioning promises for consumers? | Integration | Consumers must not break on an upgrade. | None. |
| G9 | Which operations need an off-chain data exchange (documents, private messages) and where is it stored? | Integration | Large or sensitive data stays off chain; only a hash is anchored. | Not used. |

## H. Keys and security

| # | Question | Scope | Rationale | Demo today |
|---|---|---|---|---|
| H1 | Where do signing keys live: software keystore, HSM, cloud KMS, MPC, custodian? **Gate** | Security | The single largest risk in the system; it decides who can move or mint assets. | Keystore files and a committed demo password. |
| H2 | Who holds validator, admin, minter, claim-issuer and notary keys, and how are they separated? | Security | Separation of duties prevents one compromised key from doing everything. | One admin; all demo keys public. |
| H3 | What are the approval rules for sensitive actions (multi-signature, dual control, time delays)? | Security | Prevents unilateral mint, pause or upgrade. | None. |
| H4 | How are keys generated, backed up, rotated and revoked? | Security | Defines the procedure when a key is lost or exposed. | Generated once by `init`. |
| H5 | Paladin key management: how is each node's seed protected, and how are its derivation records backed up? | Security | A seed alone does not recreate the keys (the derivation index lives in the database), so both must be protected and backed up. | Demo seeds committed. |
| H6 | What is the threat model (insider, external attacker, compromised participant, malicious notary)? | Security | Drives every control above; write it down and review it. | Not written. |
| H7 | How are secrets, certificates and TLS managed (vault, rotation, expiry alerts)? | Security | Expired or leaked certificates break or expose node links. | Self-signed demo certificates. |
| H8 | What network controls apply (segmentation, firewalls, who can reach RPC, admin APIs and the Paladin UI)? | Security | RPC and UI ports must not be reachable by untrusted networks. | Ports published to localhost, no authentication. |
| H9 | Which security assessments are required (penetration test, contract audit, threat review) and when? | Security | Required before production and again after major change. | None. |
| H10 | How are dependencies and container images vetted, pinned and scanned? | Security | Supply-chain risk; the Paladin and FireFly images and npm packages are third-party. | Pinned digests and versions; no scanning. |

## I. Operations

| # | Question | Scope | Rationale | Demo today |
|---|---|---|---|---|
| I1 | Who operates each node, and what is the support model and on-call? | Operations | A consortium chain has no single operator; responsibilities must be explicit. | A developer. |
| I2 | What are the availability targets (RTO, RPO, uptime) and how are they met? | Operations | Decides validator count, redundancy and backup frequency. | None. |
| I3 | Which platform runs it: Kubernetes, VMs, managed service? | Operations | Docker Compose on one machine is not a production topology. | Docker Compose. |
| I4 | How are node data (chain, Postgres, keystores) backed up and restored, and is a restore tested? | Operations | A backup that was never restored is not a backup. | Volumes; `reset` for a clean start. |
| I5 | What is monitored (block height, peers, validator liveness, transaction queue, node health, certificate expiry) and who is alerted? | Operations | Early warning for a stalled chain or a lagging indexer. | Health checks only. |
| I6 | How are logs and traces collected (structured logging, OpenTelemetry) and kept? | Operations | Required for incident analysis and audit. | Container logs. |
| I7 | What is the change and release process for contracts, node software and configuration? | Operations | Production changes need review, staging and rollback. | Commit to `main`. |
| I8 | Are there separate environments (dev, test, staging, production) and how is data kept apart? | Operations | Test data and test keys must never reach production. | One environment. |
| I9 | What is the incident and disaster-recovery plan for a halted chain, compromised key or lost node? | Operations | Procedures must exist before the incident. | None. |
| I10 | What is the cost model (infrastructure, licences, support, audit) and who funds it? | Operations | Sets whether the design is sustainable beyond a pilot. | Not estimated. |

## J. Performance and scale

| # | Question | Scope | Rationale | Demo today |
|---|---|---|---|---|
| J1 | What are the expected and peak transactions per second, and their growth? | Performance | Sizing starts from a real number; the demo's numbers are not a limit. | 5 TPS offered in the benchmark. |
| J2 | What latency is acceptable from submission to final? | Performance | The block period is a floor; the middleware and private paths add to it. | FireFly about 4 to 5 s average at 5 TPS, chain about 1 s. |
| J3 | What data volume per year, and how is chain and database growth managed? | Performance | Drives storage, archive nodes and pruning. | Not estimated. |
| J4 | Does the design need to scale by adding nodes, validators or parties? | Performance | More validators lower throughput; more Paladin parties multiply private-data exchange. | 1 validator, 3 Paladin nodes. |
| J5 | Has the target configuration been load-tested, including Paladin and failure cases (node down, slow peer)? | Performance | The demo's ceiling (FireFly saturates near 8 TPS here) says nothing about production hardware. | Caliper on one laptop; Paladin not benchmarked. |
| J6 | What is the performance cost of privacy (Noto versus public, Zeto proofs)? | Performance | Needs measuring in the target set-up before committing. | Not measured. |

## K. Delivery and governance

| # | Question | Scope | Rationale | Demo today |
|---|---|---|---|---|
| K1 | What is the governance model for the network (who decides on members, upgrades, disputes)? **Gate** | Delivery | Technology cannot settle disagreements between organisations; a governance agreement must exist before the first node is live. | None. |
| K2 | What is the onboarding and offboarding process for a new member? | Delivery | Covers legal, technical and key steps, and what happens to their data and nodes on exit. | Scripted onboarding of demo wallets. |
| K3 | What is the minimum viable first release and the phase plan? | Delivery | Keeps scope controlled; settle the gates first. | Phases in `docs/plan.md`. |
| K4 | What skills and team are needed (Solidity, Besu operations, FireFly, Paladin, security)? | Delivery | The stack spans several niche skills; gaps become delays. | See `docs/skills-required.md`. |
| K5 | What are the build-versus-buy and vendor choices (managed Besu, commercial FireFly or Paladin support)? | Delivery | Affects cost, support and exit options. | All self-run open source. |
| K6 | What does the demo not prove, and what must be re-done for production? | Delivery | Keeps pilot results from being mistaken for production evidence. | See each guide's "limits" section. |
| K7 | What is the test strategy for production (unit, integration, end to end, failure, security, performance)? | Delivery | Defines the exit criteria for each phase. | Unit and integration suites; no failure or security tests. |
| K8 | What are the decision log, owner and review date for each answer above? | Delivery | Decisions without owners are reopened repeatedly. | This file is the starting list. |

---

## Suggested order

1. **Gates first:** A1, A5, B1, B3, C1, D1, E6, H1, K1. If any answer is "no" or "unknown", stop and resolve it before designing further.
2. **Then the shape:** A2 to A4, C2 to C7, D2 to D5, E1 to E5, F1 to F3.
3. **Then the build and run:** G, H, I, J.
4. **Record** each answer, owner and date, and revisit it when a gate answer changes (for example, a change in D1 changes D2 to D12 and F).

## What this demo can and cannot tell you

It shows the pieces working together on one machine and gives a side-by-side of a public token and a private one. It does **not** show production-grade keys, governance, availability, authentication, multi-organisation operation or measured scale. Treat the "Demo today" column as the distance to production, not as a recommendation.
