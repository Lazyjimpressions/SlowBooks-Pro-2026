# Current verified state

**Verified:** 2026-09-09
**Upstream source:** `VonHoltenCodes/SlowBooks-Pro-2026`  
**Fork:** `Lazyjimpressions/SlowBooks-Pro-2026`  
**Baseline:** upstream v2.9.4 plus merged fork banking Phases 1-2

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
- Bank Rules attach category metadata but do not create journal entries.
- Versioned bank-review proposals preserve normalized counterparty, optional
  existing customer/vendor, class resolution, confidence, and rationale
  separately from imported evidence.
- Phase 3 adds review/correction/approval without posting. Contact creation is
  separately confirmed and duplicate-checked; approval cannot create a ledger
  entry.
- The built-in AI tool catalogue is read-only analysis/search.

## Active work

`feat/bank-review-approval` implements Phase 3 of
`docs/implementation/IMPL_BANK_REVIEW_CLASSIFICATION.md`. Phase 4 will consume
approved proposals through guarded domain posting services and retain their
class and counterparty provenance.

## Installed test app

The installed macOS application and company databases are external runtime
state. Repository changes do not affect the installed app until a new build is
installed. Never commit data copied from Application Support.
