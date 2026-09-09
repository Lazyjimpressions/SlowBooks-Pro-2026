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

- `POST /api/banking/proposals/{id}/post` is the canonical write endpoint. It
  consumes an approved proposal, validates its guarded route, and retains
  proposal, class, and counterparty provenance on the resulting transaction.
- `POST /api/banking/proposals/{id}/reverse` posts a dated reversing journal and
  opens copied proposal revisions for correction. Reconciled rows are refused.
- `POST /api/banking/transactions/{id}/post` and `POST
  /api/banking/transfers/post` remain compatibility endpoints, but they now
  require input that matches an approved proposal and delegate to the canonical
  proposal service.
- A transfer requires mutually approved, equal-and-opposite proposals from
  different linked registers and creates one balance-sheet-only journal linked
  to both.
- Both operations are idempotent. Database uniqueness on the source identity
  prevents concurrent retry requests from creating duplicate journal entries.

Direct bank expenses appear in the Expense module and retain a reviewed vendor
when one was selected. Direct income and expenses carry an assigned class on
both the journal header and lines. Customer-payment, bill-payment, and hold
routes cannot use generic posting; they wait for the appropriate subledger
application workflow.

## Rules and AI

Rules are durable deterministic memory, not a substitute for first-time
reasoning. AI handles unseen or ambiguous rows. An approved AI mapping may
offer to create a narrowly scoped rule for future occurrences.

Deterministic suggestions use this precedence:

1. unique equal-and-opposite rows in another linked register;
2. reviewed exact aliases, scoped aliases before global aliases;
3. prior approved or posted proposals with the same normalized key and
   direction;
4. existing Bank Rules;
5. one exact normalized customer or vendor name;
6. open invoice or bill amount/date/reference candidates.

`bank-text-v1` stores normalized matching keys and inspectable confidence
components separately from source text. `POST
/api/banking/transactions/{id}/suggest` creates a proposal only. Reviewed
aliases are managed through `/api/banking/counterparty-aliases`; deactivation
retains their audit history and permits a corrected replacement.

## Classification contract

Before a bank row can post, its approved proposal should identify:

- transaction intent, such as expense, direct income, customer payment, bill
  payment, transfer, owner activity, loan, or investment;
- counter-account or existing document/payment match;
- contact role and existing customer/vendor when applicable;
- class, with an explicit assigned, legacy personal/no-class, or balance-sheet
  not-applicable decision distinct from unresolved;
- confidence, rationale, and the rule or human approval that authorized it.

The imported payee and description remain immutable evidence. Clean display
names, aliases, and normalized counterparties are separate derived data.

For companies that use classes consistently, an administrator may configure a
normal active class as the default. The review UI and deterministic proposer
show that default explicitly so it can be changed before approval. The system
`Uncategorized` class remains the reporting fallback and cannot be configured
as the company default. This preserves complete class reporting without making
reviewers manually choose `Personal` on every routine transaction.

When an existing invoice, bill, payment, expense, or deposit is involved, the
banking workflow must call or link to that domain workflow. It must not create a
generic journal entry that duplicates revenue, expense, receivables, payables,
or cash.
