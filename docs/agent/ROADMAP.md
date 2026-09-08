# AI-first banking roadmap

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

- Suggest existing vendor/customer matches.
- Require review before creating contacts.
- Apply vendor/customer links in Bank Rules.
- Offer a narrow rule after an AI mapping is approved.

## Controlled automation

- Store proposal confidence, rationale, model, policy, and approver.
- Auto-post only within explicit account, amount, and confidence policies.
- Maintain an exception queue and reconciliation controls.
- Build reporting from posted journal data and disclose unposted activity.
