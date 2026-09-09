# ADR 0003: Bank review classification and counterparty linkage

**Status:** Accepted
**Date:** 2026-09-08

## Context

ADR 0002 established that imported bank rows are evidence, not journal
entries. The next banking phase must classify payors/payees, personal versus
business activity, and ledger accounts without bypassing the existing
receivables, payables, expense, deposit, transfer, or journal controls.

The current model cannot represent that review completely:

- `BankTransaction` stores source text, an optional category account, match
  status, and an optional journal link, but no contact or class decision.
- `Transaction` stores source identity, class, and job. `source_id` has
  domain-specific meaning and is not a safe generic contact field.
- Payments and Bill Payments own their customer/vendor and allocation records.
- Expenses currently encode their optional vendor in `Transaction.source_id`,
  a legacy convention that must not be extended to bank proposals.
- Bank Rules expose `vendor_id`, but the rule engine currently applies only the
  account.
- The global SQLAlchemy audit hook already records row changes and attributes
  them to a session user or `token:<label>` API principal.

## Current contract inventory

| Area | Existing record or endpoint | Contract to preserve |
|---|---|---|
| Bank evidence | `BankTransaction` | Raw imported fields remain unchanged; one optional ledger link |
| Direct bank posting | `POST /api/banking/transactions/{id}/post` | Balanced, closing-date aware, retry-safe |
| Transfers | `POST /api/banking/transfers/post` | Two equal/opposite rows, one balance-sheet journal |
| Class | `Transaction.class_id`, `TransactionLine.class_id` | Header class propagates to lines and reports |
| Expense | `POST /api/expenses` | Optional vendor; debit expense, credit paid-from account |
| Customer receipt | `POST /api/payments` | Customer, optional invoice allocations, debit cash/UF, credit AR |
| Batch receipt | `POST /api/batch-payments` | Groups invoice allocations by customer and creates Payments |
| Vendor settlement | `POST /api/bill-payments` | Vendor, bill allocations, debit AP, credit cash |
| Deposit | `POST /api/deposits` | Debit bank, credit Undeposited Funds; selected-line persistence remains a future gap |
| Contacts | Customers and Vendors | Separate tables with duplicate checks; no generic Other Name table |
| Rules | `BankRule` | Payee pattern and account; contact/class behavior is incomplete |
| AI | Analytics tools | Read-only; no banking proposal or posting authority |
| Audit/RBAC | Global middleware and audit hook | Readonly cannot write; bookkeeper can perform daily-book writes; actor is recorded |

## Decision

### 1. Use a versioned proposal as the review boundary

Add a `BankTransactionProposal` record associated with one imported bank row.
Proposal revisions preserve decisions independently from the immutable source
row. The initial contract includes:

- lifecycle status;
- transaction intent and posting route;
- normalized counterparty display name and role;
- contact resolution and optional customer or vendor;
- counter-account and explicit class resolution;
- optional invoice, bill, or paired bank-row candidate;
- proposal source, confidence, rationale, and normalizer version;
- creation, review, and posting timestamps and actor snapshots.

Only one proposal may be active for a bank row. Correcting a material proposal
creates a new revision and supersedes the old one. The global audit log records
every insert and status transition; actor snapshot fields make the decision
readable without reconstructing audit JSON.

### 2. Keep personal distinct from unresolved

`class_resolution` has three initial values:

- `unresolved`: no decision has been approved;
- `personal_no_class`: explicitly reviewed as personal and posted with
  `class_id = NULL`;
- `assigned`: business or other classed activity and a valid `class_id` is
  required.

For the initial test company, `Sch C - Lazyj` is the only business class. The
system `Uncategorized` reporting bucket remains a report fallback; it is not
used as proof that an unreviewed transaction is personal.

### 3. Represent counterparty resolution explicitly

`counterparty_resolution` has these initial values:

- `unresolved`;
- `text_only` for a reviewed counterparty that should not become a contact;
- `customer` with exactly one `customer_id`;
- `vendor` with exactly one `vendor_id`;
- `not_applicable` for transfers and similar entries.

`counterparty_role` is `payer`, `payee`, or `not_applicable`. The proposal also
stores a normalized display-name snapshot. New contacts are created only by a
separate, reviewed customer/vendor workflow with the existing duplicate check.

### 4. Add a ledger relationship table for posted counterparties

Add an additive `TransactionCounterparty` relationship instead of overloading
`Transaction.source_id`, adding an unvalidated polymorphic contact ID, or
putting customer/vendor columns on every journal line.

The initial relationship is one primary counterparty per journal transaction:

- unique `transaction_id` foreign key with cascade delete;
- role (`payer` or `payee`);
- immutable display-name snapshot;
- nullable `customer_id` and `vendor_id` foreign keys with an at-most-one
  constraint;
- optional `proposal_id` for provenance;
- creation timestamp.

Transfers and opening-balance entries normally have no counterparty row.
Aggregate deposits retain customer identity on their component Payments rather
than assigning several customers to the deposit journal. If a future workflow
needs multiple journal counterparties, the relationship can be generalized
without changing `Transaction` or `TransactionLine`.

### 5. Separate intent from posting route

The initial intent vocabulary is:

- `direct_expense`;
- `direct_income`;
- `customer_payment`;
- `bill_payment`;
- `transfer`;
- `owner_contribution`;
- `owner_draw`;
- `loan_proceeds`;
- `loan_payment`;
- `investment_activity`;
- `reimbursement`;
- `unknown`.

The posting route is a separate value: `direct`, `transfer`,
`customer_payment`, `bill_payment`, or `hold`. Separating the two prevents a
classifier from implying that every recognized intent is safe to post through
the generic two-line service.

### 6. Apply a guarded posting matrix

| Intent | Initial route | Initial policy |
|---|---|---|
| Direct expense | Direct | Allowed after account, class, and counterparty review |
| Direct income | Direct | Allowed after account, class, and counterparty review |
| Customer payment | Customer Payment | Hold until domain application is integrated |
| Bill payment | Bill Payment | Hold until domain application is integrated |
| Transfer | Transfer | Use paired bank-transfer service |
| Owner contribution/draw | Direct | Equity account required; manual review always |
| Loan proceeds | Direct | Liability account required; manual review always |
| Loan payment | Hold | Principal/interest split may be required |
| Investment activity | Hold | Basis, income, gain/loss, or transfer may be ambiguous |
| Reimbursement | Direct or hold | Direct only with an explicit receivable/payable offset |
| Unknown | Hold | Cannot approve for posting |

A candidate open invoice or bill forces the proposal to the corresponding
domain route or `hold`; it cannot be approved as generic direct income or
expense merely because the amount and sign balance.

### 7. Use deterministic suggestions before AI

Normalization, aliases, exact references, amount/date tests, register type,
direction, existing rules, and open-document searches produce inspectable
candidate scores first. AI may propose or rank ambiguous interpretations later,
but uses the same proposal contract and receives no unconstrained journal-write
capability.

## Proposal lifecycle

```text
proposed -> approved -> posted
    |           |
    |           +-> superseded (before posting only)
    +-> rejected
    +-> superseded
```

- `proposed` may be produced by a human, rule, deterministic matcher, or AI.
- `approved` is complete and eligible for its configured posting route.
- A posting failure leaves it approved and retryable.
- `posted` requires the bank row's ledger link to exist.
- `rejected` and `superseded` are historical terminal states.
- A posted correction uses reversal and a replacement proposal; the original
  proposal and journal remain in the audit trail.

## Synthetic fixture matrix

Phase tests use invented names and amounts only:

| Fixture | Expected result |
|---|---|
| `SQ *CEDAR WORKSHOP 4821` deposit | Existing customer candidate; direct income or AR hold based on open invoice |
| `NORTHSTAR OFFICE #104` withdrawal | Existing vendor and office-expense candidate |
| Same vendor on a card register | Direct expense with credit-card sign convention |
| Equal/opposite checking and savings rows | Transfer candidate; no contact or class required |
| `OWNER TRANSFER` deposit | Owner contribution; equity and manual review required |
| `LOAN SERVICING ACH` withdrawal | Loan-payment hold because a split may be required |
| `CORP REIMBURSEMENT` deposit | Receivable-offset candidate, not income by default |
| Unknown mobile deposit | Unresolved; no contact creation and no posting |

No real company name, statement description, account number, export, or amount
is copied into repository fixtures.

## Consequences

- Bank review can express payor/payee, personal/business class, and account
  coding without mutating imported evidence.
- The ledger gains a queryable counterparty association without redefining
  source identity or adding party fields to every journal line.
- Existing AR/AP services remain authoritative, preventing duplicate revenue,
  expense, receivables, payables, or cash.
- Proposal and ledger schemas require additive migrations and more joins.
- Direct posting remains deliberately narrower than classification; some
  correctly classified rows will stay on hold until later domain integration.

## Alternatives rejected

- **Store customer/vendor in `Transaction.source_id`:** rejected because that
  field identifies different source records depending on `source_type` and
  cannot enforce a contact foreign key.
- **Put customer and vendor directly on `BankTransaction`:** rejected because
  proposed classifications need revision history and an imported row may match
  an existing domain transaction without owning its contact.
- **Use blank class to mean both personal and unresolved:** rejected because it
  silently classifies unfinished work as personal.
- **Let rules or AI write journal lines directly:** rejected by ADR 0002 and the
  accounting invariants.
- **Require every statement name to become a customer or vendor:** rejected to
  avoid polluted contact lists and incorrect semantics for owners, employers,
  banks, and processors.
