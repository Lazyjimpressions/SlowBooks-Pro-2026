# Implementation Plan: Upstream 2.10 Banking Integration

**Version:** 1.0  
**Last Updated:** September 10, 2026  
**Status:** Phase 0 audit complete; implementation not started

**References:**

- [Current verified state](../agent/CURRENT_STATE.md)
- [AI-first banking roadmap](../agent/ROADMAP.md)
- [Accounting invariants](../agent/ACCOUNTING_INVARIANTS.md)
- [ADR 0001: Upstream-first public fork](../agent/decisions/0001-upstream-first-fork.md)
- [ADR 0003: Bank review classification](../agent/decisions/0003-bank-review-classification.md)
- [ADR 0004: Adopt upstream ledger banking](../agent/decisions/0004-adopt-upstream-ledger-banking.md)
- [Completed bank-review plan](IMPL_BANK_REVIEW_CLASSIFICATION.md)

---

## Objective

Integrate upstream v2.10.3 without maintaining a parallel accounting engine.
Upstream's ledger-backed register, statement matching, transfers, voids, and
reconciliation become authoritative. The fork retains and adapts its versioned
proposal, classification, class/contact, and guarded AI-policy capabilities.

This is a controlled replacement of overlapping internals. It is not a reset of
fork history, and it must not touch the installed macOS application or the test
company until disposable upgrade tests pass.

## Verified baseline

Audit date: September 10, 2026.

- Fork `main`: `f40447a`, based on upstream v2.9.4 plus completed banking
  Phases 1-6.
- Upstream `main`: `d2ae5ed`, tagged v2.10.3.
- Common ancestor: upstream v2.9.4 (`0cb9188`).
- Upstream changed 112 files since the common ancestor; the fork changed 71;
  22 paths overlap.
- Upstream adds ledger-backed banking, statement match/add/exclude workflows,
  transfer services, GL reconciliation, control-account safeguards, and later
  release maintenance.
- Upstream does not contain the fork's proposal, deterministic classification,
  generic transaction-counterparty, or expanded rule capabilities.
- Bank of America detail CSV support remains a focused upstream contribution in
  upstream PR #130.

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
- Fresh installs and existing fork databases both reach one valid Alembic head.
- No real company data, credentials, or statement exports enter fixtures or Git.

## Migration compatibility contract

The v2.10 compatibility migration for an existing fork-head database must make
the same structural changes as upstream's canonical revision, without assuming
that revision's operations ran:

- add and backfill `accounts.bank_kind`;
- add `transaction_lines.cleared` and `transaction_lines.reconciliation_id`;
- rename `bank_accounts.balance` to `legacy_balance` without treating that
  stored value as current ledger truth;
- add `bank_transactions.transaction_line_id`;
- add `reconciliations.account_id`, `beginning_balance`, and `cleared_total`, and
  make the legacy feed reference nullable; and
- link any feed that lacks a chart account to a new, non-posting bank-kind
  account using upstream's deterministic allocation rules.

It also needs fork-specific data conversion that upstream could not know about:

- for a bank row with `transaction_id`, identify exactly one line on the feed's
  linked chart account and backfill `transaction_line_id`;
- handle paired transfers by selecting the line for each row's own linked chart
  account;
- preserve posted proposal references and classify successfully backfilled rows
  as present in the books, rather than returning them to the unmatched queue;
- carry completed reconciliation state onto mapped ledger lines where the
  relationship is unambiguous; and
- report ambiguous or missing bank-side lines as migration exceptions instead
  of guessing.

Rows that were only ticked in the old side ledger and have no corresponding
ledger line cannot become cleared GL activity. Preserve their legacy evidence
and use upstream's excluded/restore treatment until reviewed.

---

## Phase 0 — Audit and integration contract 🟨

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

**Remaining before implementation:**

- [ ] Decide, with a concurrency test, whether any replacement source-uniqueness
  constraint is still required.
- [ ] Capture disposable fresh and fork-head database fixtures containing only
  synthetic data.

**Exit criteria:** one reviewed migration design covers fresh install, existing
fork upgrade, downgrade boundary, and duplicate-revision avoidance.

## Phase 1 — Merge upstream and reconcile migrations ⬜

- [ ] Create an integration branch from current fork `main` and merge
  `upstream/main` with an explicit merge commit.
- [ ] Prefer upstream implementations in banking register, posting, matching,
  transfer, reconciliation, PDF, and their tests.
- [ ] Keep upstream `e7f8a9b0c1d2_banking_on_the_ledger.py` as the canonical
  fresh-install revision.
- [ ] Add a uniquely identified compatibility migration after the fork head for
  databases whose recorded history skipped upstream's conversion operations.
- [ ] Make compatibility operations safely conditional on schema state.
- [ ] Produce exactly one Alembic head and test upgrade/downgrade on both
  synthetic database paths.
- [ ] Preserve the fork's agent docs, secret scanning, and generic BoA parser if
  PR #130 has not landed upstream.

**Exit criteria:** upstream v2.10.3 runs on a fresh database and an upgraded
synthetic fork database with no duplicate revisions, data loss, or stored-balance
dependency.

## Phase 2 — Adapt proposal and classification services ⬜

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

## Phase 3 — Dispatch approved proposals through upstream workflows ⬜

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

## Phase 4 — Consolidate UI and Bank Rules ⬜

- [ ] Extend upstream's Banking statement queue with proposal evidence,
  confidence, intent, account, class, and reviewed counterparty fields.
- [ ] Remove the competing standalone review flow after feature parity.
- [ ] Adapt scoped Bank Rules to upstream bank/credit-card identifiers and match
  states.
- [ ] Keep rule execution proposal-only and contact creation separately gated.
- [ ] Verify keyboard, empty-state, error, and bulk-action behavior.

**Exit criteria:** users have one Banking workflow for match, add, exclude,
classification, approval, and posting.

## Phase 5 — Regression, upgrade rehearsal, and controlled rollout ⬜

- [ ] Run upstream's banking invariant, register, feed-review, transfer,
  reconciliation, control-account, and migration tests.
- [ ] Port and run the fork's proposal, classification, approval, rules,
  counterparty, class, and idempotency tests.
- [ ] Run full CI, formatting, lint, dependency audit, and secret scanning.
- [ ] Build the exact merge candidate for macOS.
- [ ] Snapshot the external test database and rehearse the upgrade on a copy.
- [ ] Repeat synthetic live acceptance for personal, Schedule C, direct income,
  expense, transfer, card payment, reimbursement, text-only, AR/AP hold, match,
  exclude/restore, reconciliation, void, and retry behavior.
- [ ] Install only after the reconciliation report, trial balance, and original
  source-row checks pass.

**Exit criteria:** the integrated build passes both upstream and fork accounting
contracts and can upgrade the test company without changing unexplained
balances.

## Deferred work

- Autonomous posting thresholds and model governance
- Customer-payment and bill-payment application
- Merchant settlement batches and processor clearing
- Schedule C reporting enhancements
- Chart subaccount and register-relinking UI

These remain valuable, but adding them during the 2.10 integration would make
accounting regressions harder to isolate.

## Resuming this plan

Start with Phase 0's exact schema-operation inventory. Do not begin by resolving
the 22 overlapping source files. The first executable artifact should be a pair
of synthetic database fixtures and a migration test proving both paths to one
head. After that, merge upstream on a dedicated branch and adapt one vertical
slice: import -> proposal -> approval -> upstream add -> ledger-line link.
