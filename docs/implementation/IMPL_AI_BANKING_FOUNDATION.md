# Implementation Plan: AI Banking Foundation

**Version:** 1.5
**Last Updated:** September 9, 2026
**Status:** Initial banking foundation complete; controlled automation and
subledger application remain future work
**References:**

- [Banking automation](../agent/BANKING_AUTOMATION.md)
- [Accounting invariants](../agent/ACCOUNTING_INVARIANTS.md)
- [Roadmap](../agent/ROADMAP.md)
- [Bank review classification](IMPL_BANK_REVIEW_CLASSIFICATION.md)

---

## Session Context

- The fork includes upstream v2.9.4 (`0cb9188`) plus the merged import-balance,
  Bank of America CSV, and atomic bank-posting changes.
- Upstream fixed the UI to permit liability-linked registers.
- Imported rows now move the displayed bank-register balance exactly once.

---

## Phase 0 — Operating foundation 🟩

**Deliverables:**

- [x] Cross-platform agent entrypoints
- [x] Canonical architecture, security, workflow, and decision documents
- [x] Private AI operations repository created
- [x] Secret-handling rules defined

---

## Phase 1 — Retry-safe import balances 🟩

**Deliverables:**

- [x] Shared atomic imported-balance helper
- [x] CSV imports move balance only for new rows
- [x] OFX imports move balance only for new rows
- [x] SimpleFIN inherits the same behavior
- [x] Formatting and lint checks pass
- [x] Targeted import tests pass (45 passed)
- [x] Linux CI confirms the full suite

Local full-suite result: 1,901 passed, 8 skipped, and one unrelated macOS
OCR-engine-selection failure. The failing test expects the no-Poppler path,
while the installed native app makes an alternate macOS OCR path available.
The draft PR's Linux test-and-coverage job passes, along with dependency audit,
Gitleaks, and Docker build checks.

**Files:**

- `app/services/bank_balance.py`
- `app/services/bank_csv_import.py`
- `app/services/ofx_import.py`
- `app/services/bank_posting.py`
- `app/routes/banking.py`
- `tests/test_bank_csv_import.py`
- `tests/test_bank_posting.py`
- `tests/test_ofx_import.py`
- `tests/test_simplefin.py`

---

## Phase 2 — Posting and review API 🟩

**Deliverables:**

- [x] Proposal and review records
- [x] Idempotent domain posting endpoint
- [x] Bank-row-to-journal linkage
- [x] Transfer matching and reversal workflow

---

## Phase 3 — Contacts and reviewed proposal policy 🟩

Detailed execution is tracked in
[`IMPL_BANK_REVIEW_CLASSIFICATION.md`](IMPL_BANK_REVIEW_CLASSIFICATION.md).

**Deliverables:**

- [x] Review proposal records distinguish unresolved rows from approved
  personal/no-class activity
- [x] Required review fields: transaction intent, counter-account, contact
  role/contact, class, confidence, and rationale
- [x] Vendor/customer suggestions
- [x] Approved contact links retained on posted ledger transactions
- [x] Bank Rule contact, class, counter-account, and transaction-intent
  application
- [x] Preserve raw descriptions and store normalized matching fields separately
- [x] Post approved direct income, expense, balance-sheet activity, and
  transfers through guarded services
For the initial implementation, `Personal` may be configured as the visible
default class and `Sch C - Lazyj` is the first business class. A pure
balance-sheet transaction uses `not_applicable`; a row without an approved
proposal remains unresolved. Do not create contacts merely because a statement
contains a new name.

---

## Phase 6 — Controlled rollout 🟩

- [x] Release dependency advisory remediated and audited
- [x] Local banking, PDF, formatting, lint, migration, and full-suite gates run
- [x] Fork CI, secret scanning, dependency audit, and Docker checks passed
- [x] Exact merged commit built and validated on macOS
- [x] Test company backed up and forward-migrated to banking schema head
- [x] Live proposal, approval, posting, idempotency, reversal, transfer,
  card-payment, reimbursement, class, contact, and AR/AP-hold paths validated
- [x] Existing register balances and BoA Savings evidence verified unchanged

The controlled rollout validates the architecture boundary: AI and rules may
propose, reviewers approve, deterministic services post, and domain candidates
remain held for AR/AP application. Reversals preserve audit history while
restoring net account and reporting balances.

## Future phase — AR/AP application and merchant settlement 🔲

**Ideas recorded for later evaluation:**

- [ ] Store model identity and versioned approval-policy decisions
- [ ] Add bounded confidence/amount policies and an exception queue
- [ ] Disclose unresolved and approved-but-unposted activity in reporting
- [ ] Apply an existing unapplied customer payment to one or more invoices
  without posting cash again
- [ ] Apply an existing vendor prepayment to one or more bills without posting
  cash again
- [ ] Persist selected Undeposited Funds lines and link a combined deposit to
  its component payments
- [ ] Add lossless, versioned bank/processor description normalization
- [ ] Add merchant-clearing accounts and gross/fee/net settlement batches
- [ ] Match bank payouts to processor batches, including refunds, chargebacks,
  reserves, and fee splits
- [ ] Add AI proposals for payment application and payout composition while
  keeping approval and posting deterministic

---

## File Structure (Target State)

```text
AGENTS.md
CLAUDE.md
.cursor/rules/slowbooks-project.mdc
docs/agent/
docs/implementation/IMPL_AI_BANKING_FOUNDATION.md
app/services/bank_balance.py
```

---

## Resuming Work in a New Chat

> I'm continuing work on AI Banking Foundation. Read
> `docs/implementation/IMPL_AI_BANKING_FOUNDATION.md`, `AGENTS.md`, and
> `docs/agent/START_HERE.md`, then select one pending roadmap item and create a
> focused implementation plan before changing behavior.
