# Architecture boundaries

SlowBooks has two distinct financial data layers:

1. `bank_accounts` and `bank_transactions` provide statement ingestion,
   deduplication, categorization metadata, and reconciliation.
2. `transactions` and `transaction_lines` are the double-entry general ledger
   used by financial reports.

A bank row may eventually link to one ledger transaction through
`BankTransaction.transaction_id`. Until that link exists, categorizing the row
must not be described as posting it.

## AI boundary

AI proposes intent and mappings. Deterministic application services validate
and post. Models must not assemble unconstrained journal writes when a guarded
domain endpoint can express the transaction.

The preferred integration is a private external orchestration layer using
versioned SlowBooks APIs. Generic validation, idempotency, posting, and audit
capabilities belong in the public core.

## Installed application boundary

The source checkout, packaged app, and company database are separate. Updating
one does not silently update the others. Company data stays outside the app
bundle; source fixes require a rebuilt package or upstream release.
