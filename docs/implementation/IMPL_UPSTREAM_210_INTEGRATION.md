# Implementation Plan: Upstream 2.10 Banking Integration

**Version:** 1.2
**Last Updated:** September 12, 2026
**Status:** Phase 0 complete; clean-mirror transition ready for review

**References:**

- [Current verified state](../agent/CURRENT_STATE.md)
- [AI-first banking roadmap](../agent/ROADMAP.md)
- [Accounting invariants](../agent/ACCOUNTING_INVARIANTS.md)
- [ADR 0001: Upstream-first public fork](../agent/decisions/0001-upstream-first-fork.md)
- [ADR 0003: Bank review classification](../agent/decisions/0003-bank-review-classification.md)
- [ADR 0004: Adopt upstream ledger banking](../agent/decisions/0004-adopt-upstream-ledger-banking.md)
- [ADR 0005: Clean mirror contributions](../agent/decisions/0005-clean-mirror-contribution-model.md)
- [Completed bank-review plan](IMPL_BANK_REVIEW_CLASSIFICATION.md)

---

## Objective

Re-establish a stable upstream release as the source baseline without
maintaining a parallel accounting engine. Upstream's ledger-backed register,
statement matching, transfers, voids, and reconciliation become authoritative.
The fork retains only the versioned proposal, classification, class/contact, and
guarded AI-policy capabilities that remain useful after upstream validation.

The completed v2.9.4 work remains available as an archive, not as the base for a
forward merge. The lightly populated test company will be recreated and its
source statements re-imported; no compatibility migration will be maintained
solely for that experimental database.

## Verified baseline

Audit refreshed: September 12, 2026.

- Fork `main`: `f40447a`, based on upstream v2.9.4 plus completed banking
  Phases 1-6.
- Upstream `main`: `117fa65`, tagged v2.12.1.
- Common ancestor: upstream v2.9.4 (`0cb9188`).
- Upstream changed 112 files since the common ancestor; the fork changed 71;
  22 paths overlap.
- Upstream adds ledger-backed banking, statement match/add/exclude workflows,
  transfer services, GL reconciliation, control-account safeguards, and later
  release maintenance.
- Upstream does not contain the fork's proposal, deterministic classification,
  generic transaction-counterparty, or expanded rule capabilities.
- Bank of America detail CSV support remains represented by upstream PR #130;
  both LazyJimpressions commits are on `release/2.13.0` with authorship
  preserved while that release is gated.
- Tag `lji-v2.9.4-ai-banking-final` preserves the pre-transition fork baseline.
- PR #130 follow-up commit `b50eaba` adds a CRLF fixture derived from two real
  exports while containing only synthetic values and descriptions.

## Target architecture

```text
statement import
    -> upstream statement queue and immutable source row
    -> fork normalization, rule, and AI proposal layer
    -> explicit human or policy approval
    -> upstream match, add, transfer, void, or domain service
    -> ledger line link, reconciliation, and reporting
```

Only the ledger and existing subledgers create accounting truth. AI and rules
may propose decisions; deterministic services validate and execute them.

## Keep, replace, adapt, retire audit

| Area | Decision | Reason and required change |
|---|---|---|
| `BankTransactionProposal` lifecycle | Adapt | Unique fork capability; point posting results at upstream statement/ledger links and preserve revisions |
| Bank text normalization | Keep | Derived matching data preserves raw evidence and has no upstream equivalent |
| Deterministic suggestions | Adapt | Reuse upstream candidate matching and transfer semantics; preserve conservative AR/AP holds |
| Counterparty aliases | Keep and adapt | Useful reviewed learning; keep contact creation separately gated |
| `TransactionCounterparty` | Keep provisionally | Upstream derives names from source modules but has no generic reviewed payer/payee relation; validate report/API consumers before final schema choice |
| Explicit class resolution/default | Keep and adapt | Upstream accepts `class_id` when adding feed rows; proposal approval must retain why a class is present or absent |
| Expanded Bank Rules | Adapt | Continue producing non-posting proposals against upstream's queue and register model |
| Separate review UI | Consolidate | Add proposal fields and actions to upstream Banking UI rather than maintain two queues |
| Stored `BankAccount.balance` updates | Retire | Conflicts with upstream ledger-derived balances and `legacy_balance` conversion |
| Fork `post_bank_transaction` | Replace | Use upstream `post_bank_entry` and statement `add` contract |
| Fork paired-transfer posting | Replace | Use upstream transfer service and statement-line linkage |
| Fork reversal journals | Replace | Use upstream void safeguards, release statement links, and create a replacement proposal revision |
| Fork source uniqueness index | Reassess | Upstream links each statement row to a ledger line and guards add/match; retain only if concurrency tests prove a remaining gap |
| Reconciliation implementation | Replace | Upstream reconciles GL lines and protects completed sessions |
| Check register implementation | Replace | Upstream register is built from all ledger lines with natural balances |
| Bank of America CSV parser | Keep upstream-first | PR #130 is narrow, generic, and not supplied by v2.10.3 |
| WeasyPrint 70 fork patch | Retire | Upstream independently implemented lazy optional PDF loading |
| Documentation/security scaffolding | Keep | Cross-agent persistence and public-fork safety remain necessary |
| Phase 6 acceptance evidence | Archive | It proves the v2.9.4 behavior only; repeat acceptance for the integrated architecture |

## Required invariants

- Imported statement evidence is never rewritten by normalization or AI.
- The ledger is the only source of bank and credit-card balances.
- A statement row can link to at most one active ledger line.
- A proposal cannot post directly; approval and deterministic dispatch remain
  separate operations.
- Matching an existing ledger entry never posts cash again.
- Customer receipts, bill payments, expenses, deposits, and transfers use their
  authoritative domain services.
- Classes propagate consistently to the journal header and lines where the
  domain service supports them; pure balance-sheet transfers remain
  not-applicable.
- Contact creation remains a separate reviewed action.
- Voids preserve history and cannot bypass completed reconciliation or closing
  controls.
- The new company starts from upstream's canonical migration history and reaches
  exactly one Alembic head.
- No real company data, credentials, or statement exports enter fixtures or Git.

## Fresh-start data contract

- Take and retain a read-only, out-of-repository snapshot of the old test
  database before any application change.
- Record chart accounts, classes, bank/card definitions, useful reviewed rules,
  source-file date ranges, and statement ending balances in the private
  operations repository. Do not copy credentials or transaction data there.
- Build the replacement company from the selected stable upstream release and
  its canonical migrations only.
- Recreate users and API tokens rather than copying authentication records.
- Re-import original bank/card exports in a documented order, treating opening
  balances exactly once under upstream's ledger workflow.
- Reconcile every register to a source statement and compare the trial balance
  before porting fork-only AI behavior.
- Keep the old database and archived code available for research and discrepancy
  investigation; never combine their ledger totals with the new company.

---

## Phase 0 — Audit and transition contract 🟩

**Completed:**

- [x] Fetch and identify upstream v2.10.3.
- [x] Measure divergence and enumerate overlapping paths.
- [x] Compare upstream ledger banking with fork Phases 1-6.
- [x] Record the keep/replace/adapt/retire decision in ADR 0004.
- [x] Identify the duplicate Alembic revision `e7f8a9b0c1d2`.
- [x] Confirm that existing fork databases may already be stamped through
  `2c7d9e1f4a6b`.
- [x] Inventory the structural and fork-specific data transformations required
  for an existing fork-head database.
- [x] Choose a clean upstream database and controlled re-import instead of a
  compatibility migration for the disposable test company.
- [x] Archive current fork `main` at tag
  `lji-v2.9.4-ai-banking-final`.
- [x] Supply upstream PR #130 with a CRLF real-shape synthetic fixture.

**Exit criteria:** completed. The prior implementation is recoverable and the
new baseline does not inherit its colliding migration history.

## Phase 1 — Establish the clean upstream collaboration baseline ⬜

- [ ] Verify archive tags for both the completed application prototype and the
  final pre-realignment documentation state.
- [ ] Make the private operations repository the canonical home for our
  collaboration model, agent instructions, and AI roadmap.
- [ ] Realign public-fork `main` to current `upstream/main` using a reviewed,
  lease-protected transition; do not merge the archived application tree.
- [ ] Configure local and fork `main` to fast-forward from upstream and verify
  that both refs resolve to the same commit.
- [ ] Branch every contribution directly from current `upstream/main`; keep one
  independently mergeable change per upstream PR.
- [ ] Verify the clean mirror with upstream's proportionate test and security
  gates before beginning another feature.

**Exit criteria:** fork `main` mirrors upstream, the old implementation remains
recoverable by tag, and a documented contribution can travel from an origin
branch through upstream review and back into the synchronized mirror.

## Phase 2 — Validate a fresh upstream company after BoA release ⬜

- [ ] Wait for the stable upstream release containing the gated Bank of America
  importer. Repository synchronization does not wait on this data-migration
  gate, but company reconstruction does.

- [ ] Take a final out-of-repository snapshot of the old test database and mark
  it read-only.
- [ ] Complete the private configuration and re-import manifest without copying
  transaction data or credentials into Git.
- [ ] Create a fresh company using the untouched stable upstream build.
- [ ] Recreate chart accounts, classes, bank/card definitions, users, and API
  access intentionally.
- [ ] Re-import the original statements in the recorded order.
- [ ] Validate bank/card signs, opening balances, statement-row counts,
  transfers, exclusions, matches, ledger balances, and reconciliation.

**Exit criteria:** the unmodified upstream application can reproduce and
reconcile the test books from source exports. Any baseline defect is reported
upstream before fork-only AI code is introduced.

## Phase 3 — Adapt proposal and classification services ⬜

- [ ] Rebase proposal relationships and status transitions onto upstream
  `BankTransaction.transaction_line_id` and match states.
- [ ] Keep raw/derived field separation and the versioned normalizer.
- [ ] Make suggestion logic consume upstream match candidates and register kind.
- [ ] Preserve explicit class and counterparty resolution states.
- [ ] Keep AR/AP candidates on hold until an authoritative domain workflow is
  selected.
- [ ] Resolve the provisional `TransactionCounterparty` decision through API,
  register-payee, reporting, and deletion tests.

**Exit criteria:** every unmatched statement row can receive, revise, approve,
reject, and supersede a proposal without changing the ledger.

## Phase 4 — Dispatch approved proposals through upstream workflows ⬜

- [ ] Map approved direct decisions to upstream statement `add` and
  `post_bank_entry` behavior.
- [ ] Map transfers and credit-card payments to upstream transfer services.
- [ ] Map corrections to upstream void behavior plus a replacement proposal.
- [ ] Link the resulting upstream ledger line back to the statement row and
  proposal without a second posting identity.
- [ ] Prove idempotency and concurrency safety at the API and database layers.
- [ ] Retain closing-date, reconciliation, account-type, sign, class, and
  counterparty validation.

**Exit criteria:** approved operations post exactly once through upstream
services, while match operations never post and held domain candidates remain
unposted.

## Phase 5 — Consolidate UI and Bank Rules ⬜

- [ ] Extend upstream's Banking statement queue with proposal evidence,
  confidence, intent, account, class, and reviewed counterparty fields.
- [ ] Remove the competing standalone review flow after feature parity.
- [ ] Adapt scoped Bank Rules to upstream bank/credit-card identifiers and match
  states.
- [ ] Keep rule execution proposal-only and contact creation separately gated.
- [ ] Verify keyboard, empty-state, error, and bulk-action behavior.

**Exit criteria:** users have one Banking workflow for match, add, exclude,
classification, approval, and posting.

## Phase 6 — Regression and controlled rollout ⬜

- [ ] Run upstream's banking invariant, register, feed-review, transfer,
  reconciliation, control-account, and migration tests.
- [ ] Port and run the fork's proposal, classification, approval, rules,
  counterparty, class, and idempotency tests.
- [ ] Run full CI, formatting, lint, dependency audit, and secret scanning.
- [ ] Build the exact merge candidate for macOS.
- [ ] Re-run the Phase 2 source-file import and reconciliation matrix on the
  exact release candidate.
- [ ] Repeat synthetic live acceptance for personal, Schedule C, direct income,
  expense, transfer, card payment, reimbursement, text-only, AR/AP hold, match,
  exclude/restore, reconciliation, void, and retry behavior.
- [ ] Install only after the reconciliation report, trial balance, and original
  source-row checks pass.

**Exit criteria:** the integrated build passes both upstream and fork accounting
contracts, and the new company reconciles to its source statements without
unexplained balances.

## Deferred work

- Autonomous posting thresholds and model governance
- Customer-payment and bill-payment application
- Merchant settlement batches and processor clearing
- Schedule C reporting enhancements
- Chart subaccount and register-relinking UI

These remain valuable, but adding them during the 2.10 integration would make
accounting regressions harder to isolate.

## Resuming this plan

Resume at Phase 1 by completing the separately reviewed clean-mirror
realignment; this no longer waits for a BoA release. Continue contributing on
small branches from current upstream. When the stable BoA release ships, begin
Phase 2 from that tag, prove the untouched upstream company and re-import
baseline, and then adapt one vertical slice: import -> proposal -> approval ->
upstream add -> ledger-line link.
