# ADR 0004: Adopt upstream ledger banking and keep a thin policy fork

**Status:** Accepted  
**Date:** 2026-09-10

## Context

The fork completed its bank-review classification work against upstream v2.9.4.
Upstream v2.10.0 then replaced the old stored-balance register with a ledger-backed
banking model:

- chart accounts identify bank and credit-card registers with `bank_kind`;
- every register balance and reconciliation candidate comes from journal lines;
- imported statement rows are a review queue that can match, add, exclude, or be
  restored;
- transfers, opening balances, voids, and reconciliation use shared ledger
  services; and
- statement rows link to a specific `TransactionLine`, not merely a journal
  header.

The fork independently added versioned proposals, deterministic normalization,
class and counterparty decisions, guarded posting, reversal, and richer Bank
Rules. Keeping both posting/register implementations would create two accounting
engines and make every upstream release harder to integrate.

The histories also contain different migrations with the same Alembic revision
ID, `e7f8a9b0c1d2`. This is a schema-history collision, not an ordinary merge
conflict. Existing fork databases are already stamped through `2c7d9e1f4a6b`,
so simply retaining upstream's file would not apply its banking conversion to
those databases.

## Decision

Adopt upstream v2.10 ledger banking as the authoritative register, statement
matching, transfer, void, balance, and reconciliation implementation.

Keep the fork thin by retaining only generally useful capabilities upstream does
not yet provide:

- immutable, versioned classification proposals and approval provenance;
- deterministic normalization, conservative contact matching, and intent
  classification;
- explicit personal, assigned, unresolved, and not-applicable class decisions;
- reviewed payer/payee associations without automatic contact creation;
- richer, scoped Bank Rules that produce proposals but never post; and
- guarded AI policy whose approved decisions dispatch through upstream domain
  and ledger services.

The integrated review experience will extend upstream's statement queue. It will
not preserve a competing register or a second standalone banking workflow.

For migrations, preserve upstream `e7f8a9b0c1d2` as the canonical revision for
fresh databases. Add a uniquely identified compatibility migration after the
fork's current head that detects and applies the missing v2.10 banking schema for
existing fork databases. Re-evaluate the fork's source-uniqueness index against
upstream's statement-line link before carrying it forward. Test both a fresh
database and a database upgraded from the current fork head before any app
installation.

Private company mappings, autonomous-posting thresholds, credentials, and
financial data remain in `Lazyjimpressions/slowbooks-ai-ops`, not this public
fork.

## Capability disposition

| Fork capability | Disposition | Integration direction |
|---|---|---|
| Stored register balance maintenance | Retire | Use ledger-derived balances |
| Fork direct/transfer posting mechanics | Replace | Dispatch through upstream posting and transfer services |
| Fork proposal reversal journal logic | Replace | Use upstream void controls, then create a replacement proposal |
| Proposal persistence and lifecycle | Adapt | Link proposals to upstream statement rows and ledger results |
| Normalization and classification | Keep and adapt | Run before human review; leave source evidence unchanged |
| Class and counterparty resolution | Keep and adapt | Apply at approved add/domain dispatch; retain provenance |
| Expanded Bank Rules | Keep and adapt | Populate proposals in the upstream statement queue |
| Separate bank-review page | Consolidate | Extend upstream Banking review UI |
| Bank of America detail CSV parser | Keep upstream-first | Land focused upstream PR #130, then consume it |
| Fork PDF dependency patch | Retire | Upstream has its own lazy WeasyPrint fix |
| Agent docs and secret controls | Keep | Continue as fork maintenance infrastructure |

## Consequences

- Upstream fixes and releases remain practical to consume.
- The fork differentiates at the AI review and accounting-policy boundary rather
  than at basic bookkeeping mechanics.
- The first integration is a migration and regression project, not a feature
  sprint.
- Some completed fork code will deliberately be deleted or rewritten.
- No existing test database or installed macOS app will be upgraded until both
  database paths and accounting invariants pass on disposable copies.

