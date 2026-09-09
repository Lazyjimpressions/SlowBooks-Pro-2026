# Implementation Plan: Bank Review Classification

**Version:** 1.5
**Last Updated:** September 9, 2026
**Status:** Phase 4 complete; Phase 5 is next
**References:**

- [AI Banking Foundation](IMPL_AI_BANKING_FOUNDATION.md)
- [Banking automation method](../agent/BANKING_AUTOMATION.md)
- [Accounting invariants](../agent/ACCOUNTING_INVARIANTS.md)
- [AI-first banking roadmap](../agent/ROADMAP.md)
- [ADR 0002: Import, propose, approve, post](../agent/decisions/0002-import-propose-approve-post.md)
- [ADR 0003: Bank review classification](../agent/decisions/0003-bank-review-classification.md)

---

## Objective

Give every imported bank or credit-card row a reviewable accounting proposal
before it posts. A proposal must distinguish the transaction's intent,
counterparty, chart account, and class while preserving the source statement
text unchanged.

For the initial operating policy, `Personal` is the configurable company
default class and `Sch C - Lazyj` is the first business class. The default is
shown as a proposal that reviewers can change, rather than applied invisibly
inside ledger posting. Pure balance-sheet activity uses an explicit
`not_applicable` class decision. The system `Uncategorized` class remains a
control bucket for missing classifications, not a synonym for Personal.

This plan implements the repository's existing import -> proposal -> approval
-> guarded posting roadmap. It does not create a second accounting engine.

## Immediate outcomes

1. A review queue lists every unposted imported row and its proposal state.
2. Each proposal records transaction intent, normalized counterparty, optional
   existing customer/vendor, counter-account, class decision, confidence, and
   rationale.
3. Rules and deterministic matching can populate proposals but cannot silently
   turn an unresolved row into a posted entry.
4. Human or policy approval is explicit and auditable.
5. Approved direct income, direct expense, and transfer proposals post through
   guarded, idempotent services with their class and counterparty retained.
6. Rows that may settle open receivables or payables are identified and held
   for the appropriate domain workflow instead of being posted generically.

## Non-goals for this plan

- Applying an existing unapplied customer payment to invoices
- Applying a vendor prepayment to bills
- Merchant payout batch accounting, processor reserves, or chargebacks
- Automatically creating customers or vendors from statement text
- Autonomous high-confidence posting without a separate policy decision
- Replacing Invoice, Payment, Bill, Bill Payment, Expense, Deposit, or Transfer
  accounting services

Those items remain in the future AR/AP and merchant-settlement phase of the
parent banking roadmap.

---

## Session Context

- Retry-safe bank balances, Bank of America CSV support, and atomic direct
  posting are merged in the fork.
- `BankTransaction` retains statement text and may link to one ledger
  transaction, but it has no customer/vendor or class-decision model.
- Bank Rules currently apply an account only; their `vendor_id` value is not
  applied by the rule engine.
- The built-in AI tools are read-only and do not propose or post bank work.
- Existing AR/AP routes already validate invoice and bill allocations. They are
  authoritative for future payment-application work.
- Phase 0 selected a versioned proposal model, an additive
  `TransactionCounterparty` relationship, explicit class/contact resolution,
  and a guarded intent-to-posting matrix. See ADR 0003.

---

## Required invariants

- Imported date, amount, payee, description, source, and stable ID remain
  immutable evidence.
- Cleaned names and matching tokens are derived fields with a normalizer
  version; they never replace imported text.
- A bank row has at most one active proposal and at most one ledger posting.
- Approval requires an explicit class resolution: assigned class, an approved
  legacy personal/no-class decision, or not-applicable for pure balance-sheet
  activity.
- At most one existing customer or vendor can be selected on a proposal.
- A transfer cannot use an income or expense counter-account.
- A likely invoice or bill settlement cannot use generic direct posting.
- New contacts require a separate reviewed action.
- All writes honor roles, closing dates, Decimal arithmetic, audit attribution,
  and idempotency.
- Corrections to posted entries use reversal and replacement; they do not
  rewrite ledger history.

---

## Phase 0 — Contract and accounting design 🟩

**Deliverables:**

- [x] Inventory current bank, class, customer, vendor, Expense, Payment, Bill
  Payment, Deposit, Transfer, and journal contracts.
- [x] Define the initial transaction-intent vocabulary: direct expense, direct
  income, customer payment candidate, bill payment candidate, transfer, owner
  activity, loan, investment, reimbursement, and unknown.
- [x] Define class resolution states: `unresolved`, `personal_no_class`, and
  `assigned`; require `class_id` only for `assigned`.
- [x] Decide whether durable ledger counterparty links belong on the journal
  header, journal lines, or a relationship table. Record an ADR if this changes
  the generic ledger model.
- [x] Define proposal lifecycle and audit fields, including supersession or
  correction behavior.
- [x] Define which intent types may use direct posting and which must dispatch
  to, or wait for, a domain workflow.
- [x] Define a synthetic fixture matrix without copying live company data into
  the repository.

**Exit criteria:**

- The schema and API contract can represent personal activity, Schedule C
  activity, an existing contact, a text-only counterparty, and an unresolved
  decision without ambiguity.
- AR/AP candidates cannot accidentally become direct revenue or expense.

**Likely files:**

- `docs/agent/decisions/0003-bank-review-classification.md`
- `app/models/banking.py`
- `app/schemas/banking.py`

**Completed:** September 8, 2026 in ADR 0003. No runtime or database behavior
changed during this phase.

---

## Phase 1 — Proposal persistence and read API 🟩

**Deliverables:**

- [x] Add a migration and model for versioned bank-review proposals.
- [x] Store bank-row ID, status, intent, normalized counterparty, contact role,
  optional customer/vendor, counter-account, class resolution/class, source,
  confidence, rationale, normalizer version, and review attribution.
- [x] Enforce one active proposal per bank row and customer/vendor exclusivity.
- [x] Add unresolved and review-queue filters without changing existing import
  behavior.
- [x] Add endpoints to read a row with its active proposal and proposal history.
- [x] Keep proposal creation non-posting.

**Suggested endpoints:**

```text
GET  /api/banking/review?status=unresolved
GET  /api/banking/transactions/{id}/review
POST /api/banking/transactions/{id}/proposals
```

**Tests:**

- [x] Schema constraints and migration upgrade/downgrade
- [x] One-active-proposal concurrency behavior
- [x] Personal/no-class versus unresolved distinction
- [x] Customer/vendor exclusivity
- [x] Read-only proposal creation has no GL or register-balance effect

**Completed:** September 9, 2026. Migration `f8a9b0c1d2e3` adds the versioned
proposal table and database constraints. `GET /api/banking/review` accepts
`unresolved`, `proposed`, `approved`, `posted`, or `all`; `unresolved` means an
unposted bank row with no active proposal. Proposal creation assigns the next
revision and an actor snapshot but intentionally creates no journal entry and
does not alter a register balance.

---

## Phase 2 — Deterministic normalization and suggestions 🟩

**Deliverables:**

- [x] Add versioned normalization that preserves raw source fields.
- [x] Normalize case, spacing, punctuation, common bank prefixes, card suffixes,
  phone/location noise, and reference tokens without deleting useful evidence.
- [x] Support reviewed aliases from raw patterns to canonical counterparties.
- [x] Suggest existing customers and vendors using exact aliases first, then
  conservative normalized-name matching.
- [x] Suggest counter-accounts and classes from approved rules and prior
  reviewed decisions.
- [x] Detect equal-and-opposite transfer candidates across linked registers.
- [x] Search open invoices and bills by contact, reference, date, and amount;
  label these as candidates but do not apply them in this plan.
- [x] Produce deterministic confidence components that can be inspected without
  an LLM.

**Tests:**

- [x] Source descriptions remain byte-for-byte unchanged
- [x] Multiple noisy forms of the same synthetic merchant normalize together
- [x] Similar but distinct contacts do not auto-merge
- [x] Direction and register type prevent invalid intent suggestions
- [x] AR/AP candidates are held from direct posting

**Likely files:**

- `app/services/bank_normalization.py`
- `app/services/bank_classification.py`
- `tests/test_bank_normalization.py`
- `tests/test_bank_classification.py`

**Completed:** September 9, 2026. Normalizer `bank-text-v1` derives bounded
matching keys, display names, reference tokens, and removed-noise evidence
without changing imported fields. Reviewed aliases may be global or scoped to
a register and direction. `POST /api/banking/transactions/{id}/suggest`
persists a deterministic proposal using reviewed aliases, prior decisions,
Bank Rules, exact existing contacts, transfer pairs, and open-document
candidates. Confidence components and rationale remain inspectable; every
result stays `proposed` and no suggestion posts or creates a contact.

---

## Phase 3 — Review, correction, and approval 🟩

**Deliverables:**

- [x] Add endpoints to correct, approve, reject, and supersede proposals.
- [x] Require approval to resolve intent, counter-account, contact decision, and
  class decision.
- [x] Add a Banking review UI showing raw evidence beside derived suggestions.
- [x] Make class assignment, legacy personal/no-class, and balance-sheet
  not-applicable explicit choices rather than treating a blank as a decision.
- [x] Allow selection of existing contacts; route contact creation through the
  existing duplicate-check and create flow with separate confirmation.
- [x] Display why a proposal was suggested and whether it came from a rule,
  deterministic matcher, AI, or a human.
- [x] Add safe bulk approval only for identical, fully resolved proposals; keep
  transfers, owner activity, loans, investments, reimbursements, AR/AP
  candidates, and unusual amounts out of bulk approval initially.

**Suggested endpoints:**

```text
POST /api/banking/proposals/{id}/approve
POST /api/banking/proposals/{id}/reject
POST /api/banking/proposals/{id}/supersede
```

**Tests:**

- [x] Bookkeeper permissions and readonly rejection
- [x] Closing-date enforcement before posting, not during suggestion
- [x] Complete audit attribution
- [x] Review edits do not mutate imported evidence
- [x] UI/API parity for every required classification field

**Completed:** September 9, 2026. Reviewers can inspect immutable statement
evidence beside the full proposal, create a superseding human correction,
approve, reject, or explicitly supersede it. Approval validates the posting
route and active references but creates no journal entry. Contact creation is
a separately confirmed action with duplicate detection. Safe bulk approval is
limited to identical direct income or expense proposals at or below $1,000.
Company settings may designate an active non-system class such as `Personal`
as the visible default; deterministic suggestions record that use in their
confidence components. Transfers use `not_applicable` rather than pretending
to be Personal or Uncategorized.

---

## Phase 4 — Counterparty- and class-aware posting 🟩

**Deliverables:**

- [x] Extend guarded posting to consume an approved proposal rather than
  unconstrained journal input.
- [x] Persist the approved counterparty association on the resulting accounting
  transaction using the Phase 0 ledger decision.
- [x] Pass `Sch C - Lazyj` consistently to journal headers and lines for
  business activity.
- [x] Post approved personal activity with the explicit personal/no-class audit
  decision retained on the proposal.
- [x] Dispatch direct expenses through shared guarded journal logic and expose
  them through the Expense module; dispatch direct
  income through an appropriate guarded receipt/journal service.
- [x] Continue using the paired transfer service for transfers.
- [x] Stop and retain AR/AP candidates in review until the future application
  endpoints can perform the subledger update correctly.
- [x] Add reversal-and-replace behavior for an incorrectly posted bank row.
- [x] Preserve retry safety across approval, posting, and concurrent requests.

**Tests:**

- [x] Bank and credit-card sign conventions
- [x] Personal and Schedule C class propagation
- [x] Vendor/payee and customer/payor persistence
- [x] Balanced direct income and expense entries
- [x] Transfer pairing without P&L impact
- [x] Idempotent retries and concurrent approval
- [x] Reversal retains source and proposal history
- [x] AR/AP candidate cannot bypass the domain-workflow hold

**Completed:** September 9, 2026. `POST
/api/banking/proposals/{id}/post` consumes only approved decisions and posts
direct income, direct expenses, reviewed balance-sheet activity, or mutually
approved transfers. Header and line classes remain aligned, and a new
`TransactionCounterparty` relationship preserves the reviewed payer/payee and
optional existing customer/vendor without overloading source identity. Generic
posting endpoints now enforce the approved proposal rather than accepting an
independent classification.

Customer-payment, bill-payment, and hold routes remain non-posting until their
subledger application workflows exist. `POST
/api/banking/proposals/{id}/reverse` creates a dated reversing journal, retains
the original proposal and source evidence, detaches the bank-row ledger link,
and creates proposed replacement revisions for review. Reconciled rows cannot
be reversed through this flow. Database source uniqueness and proposal-linked
posting make retries safe, including either side of a paired transfer.

---

## Phase 5 — Bank Rules as reviewed learning 🔲

**Deliverables:**

- [ ] Extend Bank Rules to propose intent, counter-account, contact, and class
  resolution in addition to category metadata.
- [ ] Scope rules by optional register and transaction direction.
- [ ] Add conservative optional amount bounds.
- [ ] Apply rules to normalized matching fields while retaining raw-pattern
  support for exact institution text.
- [ ] Fix vendor rule application and add equivalent customer support.
- [ ] Offer, but do not silently create, a narrow rule after approval.
- [ ] Keep classification and posting policies separate.

**Tests:**

- [ ] Priority and first-match behavior
- [ ] Register and direction scoping
- [ ] Contact and class proposal application
- [ ] A matching rule does not itself post unless a separately tested policy
  authorizes it

---

## Phase 6 — Validation and controlled rollout 🔲

**Deliverables:**

- [ ] Run targeted tests, formatting, lint, migration checks, and the full test
  suite in the repository's established order.
- [ ] Pass Linux CI, dependency audit, Gitleaks, and Docker build checks.
- [ ] Merge through the fork before rebuilding the macOS application.
- [ ] Back up the test company database and install one versioned app build.
- [ ] Validate a synthetic/live-test sample covering personal expense, Schedule
  C expense, direct business income, transfer, card payment, reimbursement,
  unknown counterparty, and held AR/AP candidates.
- [ ] Re-read bank rows, proposal history, journal lines, class values, contact
  links, register balances, and financial reports after every live write.
- [ ] Confirm the existing BoA Savings postings remain unchanged unless an
  explicit reviewed backfill is performed.

**Exit criteria:**

- Every newly imported row is visibly unresolved or has a complete reviewed
  classification.
- Direct postings retain payor/payee, account, and personal/business decisions.
- No AR/AP settlement is duplicated as direct income or expense.
- Reimport and repost retries do not change balances or create duplicates.

---

## Pull request sequence

1. **Schema and review read model** — Phases 0-1
2. **Normalizer and deterministic suggestions** — Phase 2
3. **Review API and UI** — Phase 3
4. **Approved-proposal posting and reversal** — Phase 4
5. **Expanded Bank Rules** — Phase 5
6. **Packaging and live validation** — Phase 6

Each PR should be independently testable and small enough to propose upstream.
Do not combine merchant settlement or unapplied-payment application into these
PRs.

---

## File Structure (Target State)

```text
app/
  models/banking.py
  routes/banking.py
  routes/bank_rules.py
  schemas/banking.py
  schemas/bank_rules.py
  services/bank_classification.py
  services/bank_normalization.py
  services/bank_posting.py
  services/bank_rules_engine.py
  static/js/banking.js
alembic/versions/
docs/
  agent/decisions/0003-bank-review-classification.md
  implementation/IMPL_BANK_REVIEW_CLASSIFICATION.md
tests/
  test_bank_classification.py
  test_bank_normalization.py
  test_bank_posting.py
  test_bank_rules.py
```

---

## Resuming Work in a New Chat

> I'm continuing Bank Review Classification. Read
> `docs/implementation/IMPL_BANK_REVIEW_CLASSIFICATION.md`, `AGENTS.md`, and
> `docs/agent/START_HERE.md`, then begin from the first incomplete phase.
