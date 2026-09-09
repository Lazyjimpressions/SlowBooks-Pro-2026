# Current verified state

**Verified:** 2026-09-09
**Upstream source:** `VonHoltenCodes/SlowBooks-Pro-2026`  
**Fork:** `Lazyjimpressions/SlowBooks-Pro-2026`  
**Baseline:** upstream v2.9.4 plus fork banking Phases 1-5

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

PRs #14 and #15 merged Phases 4 and 5. The
`chore/phase6-controlled-rollout` branch is preparing Phase 6 by remediating
the WeasyPrint dependency advisory, running the release gates, and producing
one exact-commit macOS build before live-test validation.

## Verification status

- Merged PRs #14 and #15 passed Linux pytest, lint, Docker build, and secret
  scanning. Their dependency-audit job identified CVE-2026-55073 in
  `weasyprint==69.0`; Phase 6 updates it to 70.0 and adapts the restricted PDF
  URL fetcher to the new API.
- The Phase 6 local dependency audit is clean. Focused banking/PDF tests pass
  (74 passed), formatting and lint pass, and the two banking migrations round
  trip against an isolated SQLite database.
- The Phase 6 local full suite reports 1,985 passed and 8 skipped, plus the
  known macOS OCR engine-selection mismatch described below.
- A full downgrade to Alembic base exposes a pre-existing SQLite defect in the
  legacy Tier 3 HR downgrade at `b8c9d0e1f2a3`; current databases and the new
  banking migrations upgrade successfully to head.
- The local macOS suite has one known OCR engine-selection mismatch because
  the installed native OCR path can process the synthetic PDF when the test
  expects the no-Poppler path to reject it. Linux CI is authoritative for that
  environment-specific test.

## Installed test app

The installed macOS application and company databases are external runtime
state. Repository changes do not affect the installed app until a new build is
installed. Never commit data copied from Application Support.
