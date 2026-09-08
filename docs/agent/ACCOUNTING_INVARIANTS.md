# Accounting invariants

These conditions must hold regardless of whether a human, rule, import, or AI
initiates the work.

1. Every posted journal entry balances exactly in `Decimal` arithmetic.
2. Imported statement rows are immutable evidence; corrections use explicit
   review state or reversal, not silent history rewrites.
3. Import retries are idempotent: no duplicate row and no repeated balance
   movement.
4. A bank row can post or match at most one ledger transaction.
5. A ledger transaction linked to a bank row must use the register's linked
   asset or liability account.
6. Checking withdrawals normally credit cash; checking deposits normally
   debit cash.
7. Card charges credit card liability; card payments debit card liability.
8. Transfers affect balance-sheet accounts, never income or expense.
9. Financial reports read posted journal lines, not category labels on naked
   bank rows.
10. Closing dates, permissions, and audit attribution apply to automated work.
11. Posted corrections use reversing entries and retain the original audit
    trail.
12. Opening balances must be explicit and must not be lost when later imports
    update a register balance.
