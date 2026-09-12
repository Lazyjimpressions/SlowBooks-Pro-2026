# Current verified state

**Verified:** 2026-09-12
**Upstream source:** `VonHoltenCodes/SlowBooks-Pro-2026`  
**Fork:** `Lazyjimpressions/SlowBooks-Pro-2026`  
**Fork baseline:** upstream v2.9.4 plus completed fork banking Phases 1-6
**Current upstream:** v2.12.1 (`117fa65`); v2.13.0 release branch is in gate

## Repository model

- The public fork carries sanitized, generally useful source changes and PRs.
- The private `Lazyjimpressions/slowbooks-ai-ops` repository carries internal
  AI policy, business mappings, research, and deployment knowledge.
- The accepted target is a clean-mirror fork: `origin/main` will match
  `upstream/main`, while focused contribution branches push to `origin` and
  open pull requests against upstream. The one-time realignment has not yet
  occurred; current fork `main` remains the archived v2.9.4 prototype plus
  transition documentation.
- LazyJimpressions-specific operating policy, AI research, and durable agent
  context live in the private `slowbooks-ai-ops` repository rather than as a
  permanent delta on the public fork's `main`.

## Banking observations

- Upstream v2.9.4 allows new bank registers to link to asset or liability COA
  accounts.
- CSV supports Bank of America detail exports (including their summary
  preamble), Chase checking, Chase credit card, and two PayPal layouts.
- OFX and SimpleFIN share the FITID-based import path.
- Bank-feed rows can be posted atomically and idempotently to a counter-account;
  equal-and-opposite rows can be paired as one balance-sheet transfer.
- The fork moves `BankAccount.balance` exactly once for newly imported rows,
  preserves explicit opening balances, and leaves retries balance-neutral.
- Bank Rules can propose intent, counter-account, existing customer/vendor,
  class, and payer/payee using raw or normalized text with optional register,
  direction, and amount scope. They never approve or post.
- Versioned bank-review proposals preserve normalized counterparty, optional
  existing customer/vendor, class resolution, confidence, and rationale
  separately from imported evidence.
- Phase 4 posts only approved proposals, retains class and counterparty
  provenance, holds AR/AP candidates, and corrects posted rows by reversal and
  replacement rather than editing ledger history.
- The built-in AI tool catalogue is read-only analysis/search.

## Active work

Bank review classification Phases 0-6 remain complete for the v2.9.4 fork.
Upstream v2.10 introduced a ledger-backed register and new statement-review,
transfer, void, reconciliation, and control-account services. ADR 0004 and the
upstream 2.10 integration plan now govern the next work: adopt those upstream
mechanics and adapt only the fork's proposal, classification, class/contact, and
policy layer.

No v2.10 code has been merged into the fork and the installed macOS app has not
been changed by this audit. The completed v2.9.4 fork baseline is preserved at
tag `lji-v2.9.4-ai-banking-final`. Because the only known fork database is a
lightly populated internal test company, the chosen transition is a fresh
upstream database and controlled re-import rather than a permanent compatibility
migration for the duplicate revision `e7f8a9b0c1d2`.

Upstream PR #130 remains open as the contribution record. The maintainer
validated the real-shape fixture and copied both LazyJimpressions commits, with
authorship preserved, to `release/2.13.0` as `fa3f5a7` and `dcd3a3f`. That
release branch contains the Bank of America importer and is undergoing the
normal release gate; it is not yet the basis for a new local company.

## Verification status

- Merged PRs #14 and #15 passed Linux pytest, lint, Docker build, and secret
  scanning. Their dependency-audit job identified CVE-2026-55073 in
  `weasyprint==69.0`; Phase 6 updated it to 70.0 and adapted the restricted PDF
  URL fetcher to the new API.
- The Phase 6 local dependency audit is clean. Focused banking/PDF tests pass
  (74 passed), formatting and lint pass, and the two banking migrations round
  trip against an isolated SQLite database.
- The Phase 6 local full suite reports 1,985 passed and 8 skipped, plus the
  known macOS OCR engine-selection mismatch described below.
- A full downgrade to Alembic base exposes a pre-existing SQLite defect in the
  legacy Tier 3 HR downgrade at `b8c9d0e1f2a3`; current databases and the new
  banking migrations upgrade successfully to head. Issue #17 tracks the
  historical downgrade defect.
- The local macOS suite has one known OCR engine-selection mismatch because
  the installed native OCR path can process the synthetic PDF when the test
  expects the no-Poppler path to reject it. Linux CI is authoritative for that
  environment-specific test.
- PR #16 passed Linux pytest/coverage, lint, dependency audit, Gitleaks, and
  Docker build/start. macOS workflow run `34408086809` built merge commit
  `9d8de31924ca81137967fc855d061e32f99f7774`; its checksums, frozen bundle,
  smoke tests, PDF rendering, and native OCR validation passed.
- The exact v2.9.4 fork build migrated the test company to Alembic head
  `2c7d9e1f4a6b`. A verified out-of-repository SQLite snapshot was taken first.
- Live acceptance covered personal/no-class expense, `Sch C - Lazyj` expense,
  direct business income, transfer, credit-card payment, reimbursement,
  text-only unknown counterparty, and held AR/AP candidates. Every write was
  re-read through the API; direct and transfer posting retries were
  idempotent, reversals restored every chart-account net balance, and the
  trial balance remained balanced. Reversals intentionally retain equal gross
  debit/credit audit activity.
- The original six register balances and every existing BoA Savings row,
  posting link, and reconciliation flag remained unchanged.
- No credential, company database, bank export, or other private financial
  artifact is tracked in the public fork; PR #18's Gitleaks check passed.

## Open work

- Complete the clean-mirror realignment and upstream contribution workflow in
  `docs/implementation/IMPL_UPSTREAM_210_INTEGRATION.md`.
- Issue #4: reconcile OFX/QFX statement balance metadata and opening balances.
- Issue #5: filter Schedule C reporting by business class.
- Issue #3: expose bank-register relinking and chart subaccounts in the UI.
- Issue #17: repair the legacy Tier 3 HR SQLite downgrade.
- Controlled automation, AR/AP application, and merchant settlement require
  separate implementation plans and approval-policy decisions.

## Installed test app

The installed macOS application and company databases are external runtime
state. Repository changes do not affect the installed app until a new build is
installed. Never commit data copied from Application Support.
