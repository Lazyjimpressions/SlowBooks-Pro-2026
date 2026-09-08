# Banking automation method

## Target flow

```text
Import -> Normalize -> Deduplicate -> Rules -> AI proposal
       -> Approval policy -> Atomic posting -> Reconciliation -> Reporting
```

## Responsibility by stage

- Import preserves source date, amount, description, source, and stable ID.
- Rules handle deterministic mappings that a human has already approved.
- AI proposes transaction type, contact, counter-account, document match,
  dimensions, confidence, and a short rationale.
- The approval policy decides whether the proposal waits, auto-posts, or is
  rejected.
- A domain posting service validates signs, accounts, dates, balancing,
  idempotency, and permissions in one database transaction.
- Reconciliation compares statement evidence with posted or matched activity.

## Automation levels

1. Import only.
2. Suggest only; every proposal requires approval.
3. Auto-post exact approved rules within configured limits.
4. Auto-post high-confidence routine items; send exceptions to review.

Transfers, payroll, taxes, loans, owner activity, new contacts, unusual
amounts, and low-confidence mappings require review by default.

## Posting endpoints

- `POST /api/banking/transactions/{id}/post` posts one reviewed feed row to a
  non-bank counter-account and links the resulting journal transaction.
- `POST /api/banking/transfers/post` accepts two reviewed, equal-and-opposite
  feed rows from different linked registers and creates one balance-sheet-only
  journal transaction linked to both.
- Both operations are idempotent. Database uniqueness on the source identity
  prevents concurrent retry requests from creating duplicate journal entries.

## Rules and AI

Rules are durable deterministic memory, not a substitute for first-time
reasoning. AI handles unseen or ambiguous rows. An approved AI mapping may
offer to create a narrowly scoped rule for future occurrences.
