# Current verified state

**Verified:** 2026-09-07  
**Upstream source:** `VonHoltenCodes/SlowBooks-Pro-2026`  
**Fork:** `Lazyjimpressions/SlowBooks-Pro-2026`  
**Baseline:** v2.9.3, commit `4ba7700`

## Repository model

- The public fork carries sanitized, generally useful source changes and PRs.
- The private `Lazyjimpressions/slowbooks-ai-ops` repository carries internal
  AI policy, business mappings, research, and deployment knowledge.
- Local `main` tracks `upstream/main`; feature branches push to `origin`.

## Banking observations

- v2.9.3 allows new bank registers to link to asset or liability COA accounts.
- CSV supports Chase checking, Chase credit card, and two PayPal layouts.
- OFX and SimpleFIN share the FITID-based import path.
- Import deduplication exists, but the v2.9.3 baseline does not move
  `BankAccount.balance` for imported rows.
- Bank Rules attach category metadata but do not create journal entries.
- Imported payee text is not linked to a vendor or customer.
- The built-in AI tool catalogue is read-only analysis/search.

## Active work

`feat/ai-banking-foundation` implements import-balance consistency and the
cross-platform operating model. See
`docs/implementation/IMPL_AI_BANKING_FOUNDATION.md`.

Formatting and lint checks pass. The targeted CSV, OFX, and SimpleFIN suite
passes (45 tests). The local full suite passes 1,901 tests with 8 skips and one
environment-specific OCR failure; Linux CI remains the authoritative full-suite
gate for the draft PR. That Linux test-and-coverage gate, dependency audit,
Gitleaks scan, and Docker build all pass on draft PR #2.

## Installed test app

The installed macOS application and company databases are external runtime
state. Repository changes do not affect the installed app until a new build is
installed. Never commit data copied from Application Support.
