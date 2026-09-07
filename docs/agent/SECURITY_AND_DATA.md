# Security and data handling

## Never commit

- `.env` files containing values
- API, OAuth, session, encryption, or bank-feed credentials
- company `.db`/SQLite files and their WAL/SHM sidecars
- bank, card, PayPal, QBO, OFX, QFX, or IIF exports containing real activity
- backups, uploads, generated reports, logs, or unsanitized screenshots
- customer, vendor, employee, donor, payroll, or tax data
- raw agent transcripts containing business data

Real runtime data belongs outside the repository. Synthetic fixtures must use
invented identities, amounts, account numbers, and credentials.

## Before committing

1. Review `git status` and every staged diff.
2. Run the repository secret scan.
3. Confirm new fixtures are synthetic.
4. Confirm documentation contains placeholders rather than real tokens.
5. Inspect generated artifacts before adding them.

If a secret is committed, remove it from use immediately, rotate it, then
clean history as a separate reviewed incident response. Deleting the current
file is not sufficient because Git retains history.
