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
conflict. The only known fork database is a lightly populated internal test
company, so preserving its experimental migration history would add permanent
product complexity for little operational value.

## Decision

Use a stable upstream release as the new source baseline. Adopt upstream ledger
banking as the authoritative register, statement matching, transfer, void,
balance, and reconciliation implementation. New feature and contribution
branches start from current upstream rather than from the archived v2.9.4 fork.

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

Archive the completed fork baseline at tag
`lji-v2.9.4-ai-banking-final`. Preserve a read-only external snapshot of the old
test database, but do not ship a compatibility migration for its colliding
experimental schema. Create a fresh database on the selected stable upstream
release, recreate the small approved configuration, and re-import source
statements under the upstream ledger model. Re-evaluate every fork capability
against that clean baseline before porting it.

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
- The first integration is a clean-baseline and re-import validation project,
  not a feature sprint.
- Some completed fork code will deliberately be deleted or rewritten.
- The old test database remains available for research but is not upgraded.
- No installed macOS app or active company file changes until a stable upstream
  build passes fresh-database and re-import acceptance.
