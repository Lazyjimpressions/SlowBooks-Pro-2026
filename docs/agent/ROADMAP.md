# AI-first banking roadmap

## Immediate priority: upstream 2.10 integration

- Adopt upstream's ledger-backed bank/card register, feed matching, transfers,
  voids, reconciliation, and control-account protections.
- Resolve the duplicate Alembic revision and prove fresh-install and existing
  fork-database upgrade paths before changing the installed app.
- Adapt the completed proposal, classification, class/contact, and expanded
  Bank Rules work onto upstream's statement queue and posting services.
- Consolidate to one Banking UI and retire the fork's parallel stored-balance
  and posting implementations.

See [the phased integration plan](../implementation/IMPL_UPSTREAM_210_INTEGRATION.md)
and [ADR 0004](decisions/0004-adopt-upstream-ledger-banking.md).

## Foundation

- Keep imported register balances consistent and retry-safe.
- Preserve asset/liability account linkage for bank and card registers.
- Establish cross-agent instructions, security controls, and upstream workflow.

## Posting and review

- Add unresolved-bank-transaction queries.
- Add proposal, approve/post, reject, undo, and transfer-match endpoints.
- Link each posted bank row to exactly one journal transaction.
- Make posting atomic, idempotent, auditable, and closing-date aware.

## Contacts and deterministic learning

Implemented through Bank Review Classification Phase 5:

- Make bank review classify each row by transaction intent, counter-account,
  contact role, contact, and class before posting.
- Let a company configure a visible default class such as Personal, keep the
  system Uncategorized bucket as a control fallback, and use not-applicable for
  pure balance-sheet activity. Missing classification remains unresolved.
- Suggest existing vendor/customer matches.
- Require review before creating contacts.
- Apply vendor/customer, class, and counter-account links in Bank Rules.
- Preserve the imported payee and description as evidence while storing any
  cleaned display name or normalized counterparty separately.
- Offer a narrow rule after an AI mapping is approved.

Rules produce review proposals only. Approval and posting remain separate
policy and accounting operations.

## Controlled automation

Implemented baseline:

- Store proposal confidence, rationale, source, creator, reviewer, and approval
  timestamps.

Remaining:

- Store model identity and the versioned policy decision used for automation.
- Auto-post only within explicit account, amount, and confidence policies.
- Maintain an exception queue and reconciliation controls.
- Build reporting from posted journal data and disclose unposted activity.

## Future: receivables, payables, and merchant settlement

- Route approved bank rows through the existing Expense, Customer Payment,
  Bill Payment, Deposit, and Transfer services instead of recreating their
  accounting in the banking layer.
- Add application endpoints for existing unapplied customer receipts and
  vendor prepayments; applying them later updates subledger allocations without
  posting cash a second time.
- Persist the exact Undeposited Funds lines selected for a deposit so one bank
  deposit can be matched safely to many customer payments.
- Store immutable raw import data alongside versioned deterministic
  normalization: processor, canonical counterparty, reference tokens, gross,
  fee, net, currency, and settlement/batch identifiers.
- Model Stripe, Square, PayPal, and similar processors as merchant-clearing or
  card-receivable accounts. Match gross sales or invoice payments into the
  clearing account, then match net payouts and fees out to the bank.
- Support payout batches, partial settlements, processor reserves, refunds,
  chargebacks, and fee splits without recording revenue twice.
- Let AI propose customer/invoice or vendor/bill application and batch
  composition; require deterministic validation and configured approval before
  any write.
