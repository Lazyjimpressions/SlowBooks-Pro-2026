# Implementation Plan: AI Banking Foundation

**Version:** 1.0  
**Last Updated:** September 7, 2026  
**Status:** Phase 1 complete - Draft PR review
**References:**

- [Banking automation](../agent/BANKING_AUTOMATION.md)
- [Accounting invariants](../agent/ACCOUNTING_INVARIANTS.md)
- [Roadmap](../agent/ROADMAP.md)

---

## Session Context

- Fork and upstream remotes were synchronized at v2.9.3 (`4ba7700`).
- Upstream v2.9.3 already fixed the UI to permit liability-linked registers.
- The remaining first-phase defect is imported rows not moving the displayed
  bank-register balance.

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
- `tests/test_bank_csv_import.py`
- `tests/test_ofx_import.py`
- `tests/test_simplefin.py`

---

## Phase 2 — Posting and review API 🔲

**Deliverables:**

- [ ] Proposal and review records
- [ ] Idempotent domain posting endpoint
- [ ] Bank-row-to-journal linkage
- [ ] Transfer matching and reversal workflow

---

## Phase 3 — Contacts and AI policy 🔲

**Deliverables:**

- [ ] Vendor/customer suggestions and approved links
- [ ] Bank Rule contact application
- [ ] Confidence and automation policies
- [ ] Exception queue and reporting disclosure

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
