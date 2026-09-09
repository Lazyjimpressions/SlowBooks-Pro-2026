# Current verified state

**Verified:** 2026-09-09
**Upstream source:** `VonHoltenCodes/SlowBooks-Pro-2026`  
**Fork:** `Lazyjimpressions/SlowBooks-Pro-2026`  
**Baseline:** upstream v2.9.4 plus merged fork banking Phases 1-3

## Repository model

- The public fork carries sanitized, generally useful source changes and PRs.
- The private `Lazyjimpressions/slowbooks-ai-ops` repository carries internal
  AI policy, business mappings, research, and deployment knowledge.
- Local `main` tracks `upstream/main`; feature branches push to `origin`.

## Banking observations

- v2.9.3 allows new bank registers to link to asset or liability COA accounts.
- CSV supports Bank of America detail exports (including their summary
  preamble), Chase checking, Chase credit card, and two PayPal layouts.
- OFX and SimpleFIN share the FITID-based import path.
- Bank-feed rows can be posted atomically and idempotently to a counter-account;
  equal-and-opposite rows can be paired as one balance-sheet transfer.
- Import deduplication exists, but the v2.9.3 baseline does not move
  `BankAccount.balance` for imported rows.
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

`feat/bank-rules-reviewed-learning` implements Phase 5 of
`docs/implementation/IMPL_BANK_REVIEW_CLASSIFICATION.md` on the Phase 4 baseline
merged by PR #14. Phase 6 will merge, package, back up the test company, and
validate these banking phases in one controlled macOS build.

## Verification status

- Merged PR #14 passed Linux pytest, lint, Docker build, and secret scanning.
- Its dependency-audit job fails on the unchanged upstream
  `weasyprint==69.0` pin; the published remediation is 70.0. Resolve and test
  that dependency separately before Phase 6 claims an all-green gate.
- The local macOS suite has one known OCR engine-selection mismatch because
  the installed native OCR path can process the synthetic PDF when the test
  expects the no-Poppler path to reject it. Linux CI is authoritative for that
  environment-specific test.

## Installed test app

The installed macOS application and company databases are external runtime
state. Repository changes do not affect the installed app until a new build is
installed. Never commit data copied from Application Support.
