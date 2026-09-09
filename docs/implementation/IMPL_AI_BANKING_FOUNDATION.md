# Implementation Plan: AI Banking Foundation

**Version:** 1.1
**Last Updated:** September 8, 2026
**Status:** Phase 2 core posting complete; proposal/review and reversal remain;
Phase 3 classification is next
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

## Phase 2 — Posting and review API 🔲

**Deliverables:**

- [ ] Proposal and review records
- [x] Idempotent domain posting endpoint
- [x] Bank-row-to-journal linkage
- [ ] Transfer matching and reversal workflow (exact reviewed pairs can post;
  automated matching and reversal remain)

---

## Phase 3 — Contacts and AI policy 🔲

Detailed execution is tracked in
[`IMPL_BANK_REVIEW_CLASSIFICATION.md`](IMPL_BANK_REVIEW_CLASSIFICATION.md).

**Deliverables:**

- [x] Review proposal records distinguish unresolved rows from approved
  personal/no-class activity
- [ ] Required review fields: transaction intent, counter-account, contact
  role/contact, class, confidence, and rationale
- [ ] Vendor/customer suggestions and approved links
- [ ] Bank Rule contact, class, counter-account, and transaction-intent
  application
- [ ] Preserve raw descriptions and store normalized matching fields separately
- [ ] Post approved rows through the appropriate Expense, Customer Payment,
  Bill Payment, Deposit, or Transfer service
- [ ] Confidence and automation policies
- [ ] Exception queue and reporting disclosure

For the initial implementation, `Sch C - Lazyj` is the only business class.
An explicitly approved null class represents personal/no-class activity; a row
without an approved proposal remains unresolved. Do not create contacts merely
because a statement contains a new name.

## Future phase — AR/AP application and merchant settlement 🔲

**Ideas recorded for later evaluation:**

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
> `docs/agent/START_HERE.md` to understand the current state.
